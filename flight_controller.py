"""
Autonomous Quadcopter Flight Controller
Main module for autonomous drone control using Pixhawk 2.4.8 and Raspberry Pi

Author: [Your Name]
Date: 2026
Project: CS 153 Autonomous Drone System
"""

import time
import logging
from pymavlink import mavutil
from dataclasses import dataclass
from typing import Tuple
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('drone_flight.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DroneState:
    """Data class to hold current drone state"""
    armed: bool = False
    altitude: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0
    battery_voltage: float = 0.0
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_alt: float = 0.0
    gps_satellites: int = 0


class MotorController:
    """
    Controls motor output via Pixhawk PWM channels
    Motor layout:
    - Channel 1: Front Right
    - Channel 2: Rear Left
    - Channel 3: Front Left
    - Channel 4: Rear Right
    """
    
    def __init__(self, vehicle):
        """
        Initialize motor controller
        
        Args:
            vehicle: PyMAVLink vehicle object connected to Pixhawk
        """
        self.vehicle = vehicle
        self.min_throttle = 1000  # PWM minimum (microseconds)
        self.max_throttle = 2000  # PWM maximum (microseconds)
        self.neutral_throttle = 1500  # PWM neutral
        
        logger.info("Motor Controller initialized")
    
    def calibrate_esc(self):
        """
        Calibrate Electronic Speed Controllers (ESCs)
        IMPORTANT: Run this on first startup with battery disconnected
        """
        logger.warning("ESC Calibration sequence starting")
        logger.warning("ENSURE BATTERY IS DISCONNECTED")
        
        # Set throttle to max
        self.set_motor_all(self.max_throttle)
        logger.info("Setting throttle to MAX - connect battery now")
        time.sleep(3)
        
        # Set throttle to min
        self.set_motor_all(self.min_throttle)
        logger.info("Setting throttle to MIN - calibration complete")
        time.sleep(2)
        
        logger.info("ESC calibration complete")
    
    def set_motor_all(self, pwm_value: int):
        """
        Set all 4 motors to same PWM value
        
        Args:
            pwm_value: PWM value in microseconds (1000-2000)
        """
        if pwm_value < self.min_throttle or pwm_value > self.max_throttle:
            logger.warning(f"PWM value {pwm_value} out of range, clamping")
            pwm_value = max(self.min_throttle, min(self.max_throttle, pwm_value))
        
        for channel in range(1, 5):
            self.set_motor(channel, pwm_value)
    
    def set_motor(self, channel: int, pwm_value: int):
        """
        Set individual motor PWM output
        
        Args:
            channel: Motor channel (1-4)
            pwm_value: PWM value in microseconds (1000-2000)
        """
        if channel < 1 or channel > 4:
            logger.error(f"Invalid motor channel: {channel}")
            return False
        
        try:
            self.vehicle.channels.overrides[channel] = pwm_value
            return True
        except Exception as e:
            logger.error(f"Failed to set motor {channel}: {e}")
            return False
    
    def disarm_motors(self):
        """Set all motors to minimum throttle (safe shutdown)"""
        self.set_motor_all(self.min_throttle)
        logger.info("Motors disarmed (minimum throttle)")
    
    def arm_motors(self):
        """Prepare motors for flight (neutral throttle)"""
        self.set_motor_all(self.neutral_throttle)
        logger.info("Motors armed (neutral throttle)")


class SensorReader:
    """
    Reads sensor data from Pixhawk
    Includes: IMU (accelerometer, gyroscope), compass, barometer, GPS
    """
    
    def __init__(self, vehicle):
        """
        Initialize sensor reader
        
        Args:
            vehicle: PyMAVLink vehicle object
        """
        self.vehicle = vehicle
        self.state = DroneState()
        logger.info("Sensor Reader initialized")
    
    def read_attitude(self) -> Tuple[float, float, float]:
        """
        Read drone attitude (pitch, roll, yaw) from IMU
        
        Returns:
            Tuple of (pitch, roll, yaw) in radians
        """
        try:
            msg = self.vehicle.attitude
            pitch = msg.pitch
            roll = msg.roll
            yaw = msg.yaw
            
            self.state.pitch = pitch
            self.state.roll = roll
            self.state.yaw = yaw
            
            return pitch, roll, yaw
        except Exception as e:
            logger.error(f"Failed to read attitude: {e}")
            return 0.0, 0.0, 0.0
    
    def read_altitude(self) -> float:
        """
        Read current altitude from barometer
        
        Returns:
            Altitude in meters (relative to takeoff)
        """
        try:
            altitude = self.vehicle.location.global_relative_frame.alt
            self.state.altitude = altitude
            return altitude
        except Exception as e:
            logger.error(f"Failed to read altitude: {e}")
            return 0.0
    
    def read_battery(self) -> float:
        """
        Read battery voltage
        
        Returns:
            Battery voltage in volts
        """
        try:
            voltage = self.vehicle.battery.voltage
            self.state.battery_voltage = voltage
            return voltage
        except Exception as e:
            logger.error(f"Failed to read battery: {e}")
            return 0.0
    
    def read_gps(self) -> Tuple[float, float, float, int]:
        """
        Read GPS position and satellite count
        
        Returns:
            Tuple of (latitude, longitude, altitude, satellite_count)
        """
        try:
            loc = self.vehicle.location.global_frame
            lat = loc.lat
            lon = loc.lng
            alt = loc.alt
            sats = self.vehicle.gps_0.satellites_visible
            
            self.state.gps_lat = lat
            self.state.gps_lon = lon
            self.state.gps_alt = alt
            self.state.gps_satellites = sats
            
            return lat, lon, alt, sats
        except Exception as e:
            logger.error(f"Failed to read GPS: {e}")
            return 0.0, 0.0, 0.0, 0
    
    def get_state(self) -> DroneState:
        """Get current drone state"""
        return self.state
    
    def print_state(self):
        """Print current state for debugging"""
        logger.info(f"Attitude: P={self.state.pitch:.2f} R={self.state.roll:.2f} Y={self.state.yaw:.2f}")
        logger.info(f"Altitude: {self.state.altitude:.2f}m")
        logger.info(f"Battery: {self.state.battery_voltage:.2f}V")
        logger.info(f"GPS: ({self.state.gps_lat:.6f}, {self.state.gps_lon:.6f}) Sats: {self.state.gps_satellites}")


class FlightController:
    """
    Main flight controller
    Manages motor control and sensor reading
    """
    
    def __init__(self, connection_string: str = '/dev/ttyUSB0', baudrate: int = 115200):
        """
        Initialize flight controller
        
        Args:
            connection_string: Serial port connection to Pixhawk
            baudrate: Serial communication speed
        """
        logger.info(f"Connecting to Pixhawk on {connection_string} at {baudrate} baud...")
        
        try:
            self.vehicle = mavutil.mavlink_connection(connection_string, baud=baudrate)
            self.vehicle.wait_heartbeat(timeout=10)
            logger.info("Pixhawk connection established")
            
            self.motors = MotorController(self.vehicle)
            self.sensors = SensorReader(self.vehicle)
            
            # Safety: disarm motors on startup
            self.motors.disarm_motors()
            
        except Exception as e:
            logger.error(f"Failed to connect to Pixhawk: {e}")
            logger.error("Ensure Pixhawk is connected via USB and powered")
            sys.exit(1)
    
    def test_motors(self, duration: float = 2.0):
        """
        Test motor response (slowly increases throttle)
        SAFETY: Only run in safe environment with propellers OFF
        
        Args:
            duration: Test duration in seconds
        """
        logger.warning("MOTOR TEST - ENSURE PROPELLERS ARE REMOVED")
        input("Press Enter to continue (or Ctrl+C to cancel)...")
        
        logger.info("Starting motor test...")
        start_time = time.time()
        pwm_value = 1000
        
        while time.time() - start_time < duration:
            pwm_value += 10  # Gradually increase
            self.motors.set_motor_all(pwm_value)
            logger.info(f"PWM: {pwm_value}")
            time.sleep(0.1)
        
        # Return to safe state
        self.motors.disarm_motors()
        logger.info("Motor test complete")
    
    def test_sensors(self, duration: float = 5.0):
        """
        Read and display sensor data for verification
        
        Args:
            duration: How long to read sensors (seconds)
        """
        logger.info(f"Reading sensors for {duration} seconds...")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            self.sensors.read_attitude()
            self.sensors.read_altitude()
            self.sensors.read_battery()
            self.sensors.read_gps()
            self.sensors.print_state()
            time.sleep(1.0)
        
        logger.info("Sensor test complete")
    
    def shutdown(self):
        """Safe shutdown - disarm motors and close connection"""
        logger.info("Shutting down...")
        self.motors.disarm_motors()
        self.vehicle.close()
        logger.info("Flight controller shutdown complete")


def main():
    """
    Main entry point - test basic functionality
    """
    logger.info("=== Autonomous Quadcopter Flight Controller ===")
    
    try:
        # Initialize flight controller
        fc = FlightController()
        
        # Test sensors first (safer than motors)
        logger.info("\n1. Testing sensors...")
        fc.test_sensors(duration=5.0)
        
        # Test motors (WITHOUT PROPELLERS)
        logger.info("\n2. Testing motors...")
        fc.test_motors(duration=2.0)
        
        logger.info("\nAll tests complete!")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        fc.shutdown()


if __name__ == "__main__":
    main()
