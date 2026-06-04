"""
Main Autonomous Flight Controller
Complete autonomous flight system orchestrating:
- Flight control (Pixhawk)
- Autonomous navigation (GPS waypoints)
- Data logging (telemetry + observations)
- AI analysis (Claude API)
- Report generation

This is the primary entry point for autonomous drone missions.

Usage:
    python autonomous_flight.py --mission waypoints.csv
    python autonomous_flight.py --test-flight
"""

import argparse
import logging
import time
import sys
from pathlib import Path
from datetime import datetime

# Import our modules
from flight_controller import FlightController
from stabilization_controller import StabilizationController
from autonomous_mission import AutonomousMission, Waypoint
from data_logger import FlightDataLogger, FlightRecord, ObservationCollector
from ai_analysis import AnalysisReport
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/autonomous_flight_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutonomousFlightSystem:
    """
    Complete autonomous drone flight system
    Integrates all components for end-to-end autonomous missions
    """
    
    def __init__(self, flight_name: str = None):
        """
        Initialize autonomous flight system
        
        Args:
            flight_name: Custom identifier for this flight
        """
        logger.info("=" * 60)
        logger.info("AUTONOMOUS DRONE FLIGHT SYSTEM INITIALIZATION")
        logger.info("=" * 60)
        
        self.flight_name = flight_name or datetime.now().strftime("FLIGHT_%Y%m%d_%H%M%S")
        
        try:
            # Initialize flight controller
            logger.info("Initializing Flight Controller...")
            self.flight_controller = FlightController(
                connection_string=config.PIXHAWK_PORT,
                baudrate=config.PIXHAWK_BAUDRATE
            )
            
            # Initialize stabilization
            logger.info("Initializing Stabilization Controller...")
            self.stabilization = StabilizationController()
            
            # Initialize autonomous mission
            logger.info("Initializing Autonomous Mission Planner...")
            self.mission = AutonomousMission(
                stabilization_controller=self.stabilization,
                sensor_reader=self.flight_controller.sensors,
                motor_controller=self.flight_controller.motors
            )
            
            # Initialize data logging
            logger.info("Initializing Data Logger...")
            self.data_logger = FlightDataLogger(self.flight_name)
            self.observation_collector = ObservationCollector(self.data_logger)
            
            logger.info("✓ All systems initialized successfully")
            logger.info(f"Flight ID: {self.flight_name}")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            sys.exit(1)
    
    def preflight_checks(self) -> bool:
        """
        Perform preflight safety checks
        
        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("\nRunning Preflight Checks...")
        
        checks_passed = 0
        checks_failed = 0
        
        # Check battery voltage
        battery = self.flight_controller.sensors.read_battery()
        if battery > config.MIN_BATTERY_VOLTAGE:
            logger.info(f"✓ Battery voltage: {battery:.2f}V")
            checks_passed += 1
        else:
            logger.error(f"✗ Battery voltage CRITICAL: {battery:.2f}V (min: {config.MIN_BATTERY_VOLTAGE}V)")
            checks_failed += 1
        
        # Check GPS lock
        lat, lon, alt, sats = self.flight_controller.sensors.read_gps()
        if sats >= config.MIN_GPS_SATELLITES:
            logger.info(f"✓ GPS lock: {sats} satellites")
            checks_passed += 1
        else:
            logger.error(f"✗ GPS lock FAILED: {sats} satellites (min: {config.MIN_GPS_SATELLITES})")
            checks_failed += 1
        
        # Check compass
        pitch, roll, yaw = self.flight_controller.sensors.read_attitude()
        logger.info(f"✓ Compass initialized: yaw={yaw:.2f}")
        checks_passed += 1
        
        # Check altitude sensor
        altitude = self.flight_controller.sensors.read_altitude()
        logger.info(f"✓ Barometer working: altitude={altitude:.2f}m")
        checks_passed += 1
        
        logger.info(f"\nPreflight Result: {checks_passed} PASS, {checks_failed} FAIL")
        
        if checks_failed == 0:
            logger.info("✓ ALL SYSTEMS GO - SAFE TO LAUNCH")
            return True
        else:
            logger.error("✗ LAUNCH ABORTED - CRITICAL FAILURES")
            return False
    
    def control_loop(self, loop_rate: float = 50.0):
        """
        Main flight control loop
        Runs continuously during autonomous flight
        
        Args:
            loop_rate: Control frequency in Hz (50Hz default)
        """
        loop_interval = 1.0 / loop_rate
        last_time = time.time()
        
        logger.info(f"\nStarting control loop at {loop_rate}Hz")
        
        while True:
            current_time = time.time()
            dt = current_time - last_time
            
            # Read sensors
            pitch, roll, yaw = self.flight_controller.sensors.read_attitude()
            altitude = self.flight_controller.sensors.read_altitude()
            lat, lon, alt, sats = self.flight_controller.sensors.read_gps()
            battery = self.flight_controller.sensors.read_battery()
            
            # Update mission state
            mission_running = self.mission.update_mission()
            
            if not mission_running:
                logger.info("Mission complete")
                break
            
            # Get attitude correction from mission planner
            pitch_correction, roll_correction, yaw_correction = \
                self.mission.calculate_attitude_correction()
            
            # Set target attitude
            self.stabilization.set_target_attitude(
                pitch=pitch_correction,
                roll=roll_correction,
                yaw=yaw_correction
            )
            
            # Calculate motor outputs
            throttle = 0  # TODO: Implement throttle control for altitude
            motor_outputs = self.stabilization.calculate_motor_outputs(
                pitch=pitch,
                roll=roll,
                yaw=yaw,
                throttle=throttle
            )
            
            # Apply motor commands
            for i, pwm in enumerate(motor_outputs, 1):
                self.flight_controller.motors.set_motor(i, int(pwm))
            
            # Log telemetry
            record = FlightRecord(
                timestamp=current_time,
                epoch_time=datetime.now().isoformat(),
                gps_lat=lat,
                gps_lon=lon,
                altitude=altitude,
                gps_satellites=sats,
                pitch=pitch,
                roll=roll,
                yaw=yaw,
                battery_voltage=battery,
                motor_1_pwm=int(motor_outputs[0]),
                motor_2_pwm=int(motor_outputs[1]),
                motor_3_pwm=int(motor_outputs[2]),
                motor_4_pwm=int(motor_outputs[3]),
                mission_state=self.mission.mission_state.name,
                waypoint_index=self.mission.current_waypoint_idx,
                distance_to_waypoint=self.mission.distance_to_waypoint()
            )
            self.data_logger.log_telemetry(record)
            
            # Safety checks
            if battery < config.CRITICAL_BATTERY_VOLTAGE:
                logger.warning("CRITICAL BATTERY - EMERGENCY LANDING")
                self.mission.abort_mission()
            
            if altitude > config.MAX_ALTITUDE:
                logger.warning("MAX ALTITUDE EXCEEDED - DESCENDING")
                # TODO: Implement descent logic
            
            # Rate limiting
            elapsed = time.time() - current_time
            sleep_time = loop_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            last_time = current_time
    
    def fly_mission(self, waypoints_file: str = None, waypoints: list = None):
        """
        Execute complete autonomous mission
        
        Args:
            waypoints_file: CSV file with waypoints
            waypoints: List of Waypoint objects
        """
        logger.info("\n" + "=" * 60)
        logger.info("AUTONOMOUS MISSION EXECUTION")
        logger.info("=" * 60)
        
        try:
            # Load mission
            if waypoints_file:
                logger.info(f"Loading mission from: {waypoints_file}")
                self.mission.load_mission_from_file(waypoints_file)
            elif waypoints:
                logger.info(f"Loading {len(waypoints)} waypoints")
                self.mission.load_mission(waypoints)
            else:
                logger.error("No waypoints provided")
                return False
            
            # Preflight checks
            if not self.preflight_checks():
                return False
            
            # Confirm launch
            logger.warning("\n⚠️  READY TO LAUNCH - CONFIRM TO PROCEED")
            logger.warning("Press Ctrl+C to abort, or ENTER to launch")
            try:
                input()
            except KeyboardInterrupt:
                logger.info("Launch aborted by user")
                return False
            
            # Start mission
            logger.info("\n🚀 LAUNCHING AUTONOMOUS MISSION")
            self.mission.start_mission()
            
            # Run control loop
            self.control_loop()
            
            # Finalize flight
            logger.info("\n✓ Mission complete - finalizing data")
            self.data_logger.finalize_flight(success=True)
            
            # Generate analysis report
            logger.info("Generating AI analysis report...")
            report_gen = AnalysisReport(
                self.flight_name,
                self.data_logger.observations
            )
            report_path = f"reports/{self.flight_name}_report.md"
            Path("reports").mkdir(exist_ok=True)
            report_gen.generate_markdown_report(report_path)
            logger.info(f"✓ Report saved to: {report_path}")
            
            # Print summary
            summary = self.data_logger.get_flight_summary()
            logger.info("\n" + "=" * 60)
            logger.info("FLIGHT SUMMARY")
            logger.info("=" * 60)
            for key, value in summary.items():
                if key != 'observations':
                    logger.info(f"{key}: {value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Mission failed: {e}", exc_info=True)
            self.data_logger.finalize_flight(success=False)
            return False
        
        finally:
            # Shutdown
            self.shutdown()
    
    def test_flight(self):
        """
        Test autonomous flight with simple up-down maneuver
        """
        logger.info("\nStarting TEST FLIGHT")
        
        try:
            # Takeoff
            logger.info("Climbing to 5 meters...")
            start_time = time.time()
            while time.time() - start_time < 10:
                altitude = self.flight_controller.sensors.read_altitude()
                if altitude > 5.0:
                    break
                time.sleep(0.1)
            
            # Hover
            logger.info("Hovering for 5 seconds...")
            time.sleep(5)
            
            # Land
            logger.info("Landing...")
            start_time = time.time()
            while time.time() - start_time < 15:
                altitude = self.flight_controller.sensors.read_altitude()
                if altitude < 0.5:
                    break
                time.sleep(0.1)
            
            logger.info("✓ Test flight complete")
            return True
            
        except Exception as e:
            logger.error(f"Test flight failed: {e}")
            return False
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Safe shutdown"""
        logger.info("\nShutting down...")
        self.flight_controller.motors.disarm_motors()
        self.flight_controller.shutdown()
        logger.info("✓ Shutdown complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Autonomous Drone Flight Controller"
    )
    
    parser.add_argument(
        '--mission',
        type=str,
        help='Path to waypoints CSV file'
    )
    
    parser.add_argument(
        '--test-flight',
        action='store_true',
        help='Run test flight (simple up-down maneuver)'
    )
    
    parser.add_argument(
        '--test-sensors',
        action='store_true',
        help='Test sensor readings only'
    )
    
    parser.add_argument(
        '--flight-name',
        type=str,
        help='Custom flight identifier'
    )
    
    args = parser.parse_args()
    
    # Test sensors only
    if args.test_sensors:
        logger.info("Testing sensors...")
        fc = FlightController()
        fc.test_sensors(duration=5.0)
        fc.shutdown()
        return
    
    # Create flight system
    system = AutonomousFlightSystem(flight_name=args.flight_name)
    
    # Run test flight
    if args.test_flight:
        system.test_flight()
    
    # Run mission
    elif args.mission:
        system.fly_mission(waypoints_file=args.mission)
    
    else:
        logger.info("No mission specified. Use --mission <file> or --test-flight")
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
