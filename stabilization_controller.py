"""
PID Controller Module
Implements PID control loops for drone stabilization

Used for:
- Pitch stabilization (forward/backward tilt)
- Roll stabilization (left/right tilt)
- Yaw stabilization (rotation)
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PIDGains:
    """PID controller tuning parameters"""
    kp: float = 1.0  # Proportional gain
    ki: float = 0.1  # Integral gain
    kd: float = 0.5  # Derivative gain


class PIDController:
    """
    PID (Proportional-Integral-Derivative) controller
    
    Used to calculate control output based on error signal
    Output = Kp*error + Ki*integral(error) + Kd*derivative(error)
    """
    
    def __init__(self, name: str, gains: PIDGains, setpoint: float = 0.0,
                 output_min: float = -100.0, output_max: float = 100.0):
        """
        Initialize PID controller
        
        Args:
            name: Controller name (for logging)
            gains: PID tuning parameters (Kp, Ki, Kd)
            setpoint: Desired target value
            output_min: Minimum output value
            output_max: Maximum output value
        """
        self.name = name
        self.gains = gains
        self.setpoint = setpoint
        self.output_min = output_min
        self.output_max = output_max
        
        # State variables
        self.integral_error = 0.0
        self.last_error = 0.0
        self.last_time = time.time()
        
        logger.info(f"PID Controller '{name}' initialized: Kp={gains.kp}, Ki={gains.ki}, Kd={gains.kd}")
    
    def update(self, current_value: float, dt: Optional[float] = None) -> float:
        """
        Calculate PID output
        
        Args:
            current_value: Current measured value
            dt: Time since last update (seconds). If None, calculated automatically
        
        Returns:
            Control output value
        """
        current_time = time.time()
        if dt is None:
            dt = max(0.001, current_time - self.last_time)  # Prevent division by zero
        
        self.last_time = current_time
        
        # Calculate error
        error = self.setpoint - current_value
        
        # Proportional term
        p_term = self.gains.kp * error
        
        # Integral term (accumulate error over time)
        self.integral_error += error * dt
        # Anti-windup: limit integral to prevent saturation
        self.integral_error = max(-100, min(100, self.integral_error))
        i_term = self.gains.ki * self.integral_error
        
        # Derivative term (rate of change)
        if dt > 0:
            d_term = self.gains.kd * (error - self.last_error) / dt
        else:
            d_term = 0.0
        
        self.last_error = error
        
        # Total output
        output = p_term + i_term + d_term
        
        # Clamp output to limits
        output = max(self.output_min, min(self.output_max, output))
        
        return output
    
    def set_setpoint(self, setpoint: float):
        """Change the target setpoint"""
        self.setpoint = setpoint
    
    def set_gains(self, gains: PIDGains):
        """Update PID tuning parameters"""
        self.gains = gains
        logger.info(f"PID '{self.name}' gains updated: Kp={gains.kp}, Ki={gains.ki}, Kd={gains.kd}")
    
    def reset(self):
        """Reset integral and derivative terms"""
        self.integral_error = 0.0
        self.last_error = 0.0
        self.last_time = time.time()
    
    def __repr__(self):
        return f"PID(name={self.name}, Kp={self.gains.kp}, Ki={self.gains.ki}, Kd={self.gains.kd})"


class StabilizationController:
    """
    Flight stabilization using PID controllers
    Controls pitch, roll, and yaw to maintain level flight
    """
    
    def __init__(self):
        """Initialize all stabilization PID loops"""
        
        # Pitch controller (forward/backward tilt)
        self.pitch_pid = PIDController(
            name="Pitch",
            gains=PIDGains(kp=1.5, ki=0.1, kd=0.8),
            setpoint=0.0,  # Goal: level pitch (0 radians)
            output_min=-100,
            output_max=100
        )
        
        # Roll controller (left/right tilt)
        self.roll_pid = PIDController(
            name="Roll",
            gains=PIDGains(kp=1.5, ki=0.1, kd=0.8),
            setpoint=0.0,  # Goal: level roll (0 radians)
            output_min=-100,
            output_max=100
        )
        
        # Yaw controller (rotation)
        self.yaw_pid = PIDController(
            name="Yaw",
            gains=PIDGains(kp=2.0, ki=0.05, kd=0.5),
            setpoint=0.0,  # Goal: maintain yaw direction
            output_min=-100,
            output_max=100
        )
        
        logger.info("Stabilization Controller initialized with 3 PID loops")
    
    def calculate_motor_outputs(self, pitch: float, roll: float, yaw: float,
                               throttle: float) -> list:
        """
        Calculate motor PWM outputs for stabilization
        
        Args:
            pitch: Current pitch angle (radians)
            roll: Current roll angle (radians)
            yaw: Current yaw angle (radians)
            throttle: Base throttle level (0-1000, where 500=hover)
        
        Returns:
            List of 4 motor PWM values [motor1, motor2, motor3, motor4]
        """
        
        # Update PID controllers
        pitch_correction = self.pitch_pid.update(pitch)
        roll_correction = self.roll_pid.update(roll)
        yaw_correction = self.yaw_pid.update(yaw)
        
        # Motor layout:
        # Motor 1: Front Right    (affected by pitch-, roll+, yaw+)
        # Motor 2: Rear Left      (affected by pitch+, roll+, yaw-)
        # Motor 3: Front Left     (affected by pitch-, roll-, yaw-)
        # Motor 4: Rear Right     (affected by pitch+, roll-, yaw+)
        
        # Base PWM (neutral = 1500, range 1000-2000)
        base = 1500 + throttle
        
        # Apply corrections
        motor1 = base - pitch_correction + roll_correction + yaw_correction
        motor2 = base + pitch_correction + roll_correction - yaw_correction
        motor3 = base - pitch_correction - roll_correction - yaw_correction
        motor4 = base + pitch_correction - roll_correction + yaw_correction
        
        # Clamp all motors to valid PWM range (1000-2000)
        motors = [
            max(1000, min(2000, motor1)),
            max(1000, min(2000, motor2)),
            max(1000, min(2000, motor3)),
            max(1000, min(2000, motor4))
        ]
        
        return motors
    
    def set_target_attitude(self, pitch: float = 0.0, roll: float = 0.0, yaw: float = 0.0):
        """
        Set desired drone attitude (tilt angles)
        
        Args:
            pitch: Target pitch angle (radians, negative=forward)
            roll: Target roll angle (radians, negative=left)
            yaw: Target yaw angle (radians)
        """
        self.pitch_pid.set_setpoint(pitch)
        self.roll_pid.set_setpoint(roll)
        self.yaw_pid.set_setpoint(yaw)
        logger.info(f"Target attitude set: pitch={pitch:.3f}, roll={roll:.3f}, yaw={yaw:.3f}")
    
    def tune_gains(self, controller_name: str, kp: float, ki: float, kd: float):
        """
        Tune PID gains (used for testing different values)
        
        Args:
            controller_name: "pitch", "roll", or "yaw"
            kp, ki, kd: New gain values
        """
        gains = PIDGains(kp=kp, ki=ki, kd=kd)
        
        if controller_name.lower() == "pitch":
            self.pitch_pid.set_gains(gains)
        elif controller_name.lower() == "roll":
            self.roll_pid.set_gains(gains)
        elif controller_name.lower() == "yaw":
            self.yaw_pid.set_gains(gains)
        else:
            logger.error(f"Unknown controller: {controller_name}")
    
    def reset(self):
        """Reset all PID controllers"""
        self.pitch_pid.reset()
        self.roll_pid.reset()
        self.yaw_pid.reset()
        logger.info("All stabilization controllers reset")


# Example tuning parameters (WILL NEED TESTING AND ADJUSTMENT)
# These are conservative starting values - will need to be tuned on real drone
DEFAULT_STABILIZATION_GAINS = {
    'pitch': PIDGains(kp=1.5, ki=0.1, kd=0.8),
    'roll': PIDGains(kp=1.5, ki=0.1, kd=0.8),
    'yaw': PIDGains(kp=2.0, ki=0.05, kd=0.5)
}


if __name__ == "__main__":
    # Basic test of PID controller
    logging.basicConfig(level=logging.INFO)
    
    controller = StabilizationController()
    
    print("\n=== Stabilization Controller Test ===")
    print("Simulating drone tilting forward (pitch increases)...")
    
    # Simulate drone pitching forward
    for i in range(10):
        pitch = i * 0.1  # Gradually increase pitch
        motor_outputs = controller.calculate_motor_outputs(
            pitch=pitch,
            roll=0.0,
            yaw=0.0,
            throttle=0
        )
        print(f"Pitch: {pitch:.2f}rad, Motors: {[int(m) for m in motor_outputs]}")
        time.sleep(0.1)
    
    print("Test complete")
