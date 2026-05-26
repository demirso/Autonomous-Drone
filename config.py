"""
Configuration File for Autonomous Quadcopter
Adjust these values based on your specific drone hardware and environment
"""

# ============================================================================
# HARDWARE CONFIGURATION
# ============================================================================

# Serial connection to Pixhawk
PIXHAWK_PORT = '/dev/ttyUSB0'
PIXHAWK_BAUDRATE = 115200

# Motor PWM ranges (microseconds)
PWM_MIN = 1000        # Minimum throttle
PWM_MAX = 2000        # Maximum throttle
PWM_NEUTRAL = 1500    # Neutral point (estimated hover)

# Motor layout
MOTOR_LAYOUT = {
    1: 'Front Right',
    2: 'Rear Left',
    3: 'Front Left',
    4: 'Rear Right'
}

# ============================================================================
# PID TUNING PARAMETERS
# ============================================================================

# Pitch stabilization (forward/backward)
PITCH_PID = {
    'kp': 1.5,    # Proportional gain
    'ki': 0.1,    # Integral gain
    'kd': 0.8     # Derivative gain
}

# Roll stabilization (left/right)
ROLL_PID = {
    'kp': 1.5,
    'ki': 0.1,
    'kd': 0.8
}

# Yaw stabilization (rotation)
YAW_PID = {
    'kp': 2.0,
    'ki': 0.05,
    'kd': 0.5
}

# Note: These are CONSERVATIVE starting values
# You will almost certainly need to retune these for your specific drone
# Tuning procedure:
# 1. Start with Kp only (Ki=0, Kd=0)
# 2. Increase Kp until response is quick but not oscillating
# 3. Add Kd to reduce oscillations
# 4. Add Ki to eliminate steady-state error

# ============================================================================
# FLIGHT PARAMETERS
# ============================================================================

# Default target attitude (radians)
TARGET_PITCH = 0.0    # 0 = level
TARGET_ROLL = 0.0     # 0 = level
TARGET_YAW = 0.0      # 0 = hold current heading

# Throttle levels
THROTTLE_HOVER = 0      # Throttle to maintain altitude (0 = neutral)
THROTTLE_CLIMB = 100    # Throttle to climb
THROTTLE_DESCENT = -100 # Throttle to descend

# Maximum attitude angles (radians, ~1.2 rad = 45 degrees)
MAX_PITCH = 0.8
MAX_ROLL = 0.8
MAX_YAW_RATE = 1.0

# ============================================================================
# SAFETY PARAMETERS
# ============================================================================

# Altitude limits
MIN_ALTITUDE = 0.5      # Don't fly below 0.5m
MAX_ALTITUDE = 100.0    # Don't fly above 100m

# Battery safety
MIN_BATTERY_VOLTAGE = 10.5  # RTH if battery < 10.5V (3S LiPo warning)
CRITICAL_BATTERY_VOLTAGE = 9.6  # Emergency land if < 9.6V

# GPS minimum satellites for autonomous flight
MIN_GPS_SATELLITES = 6

# Timeout for losing GPS (seconds)
GPS_TIMEOUT = 5.0

# ============================================================================
# SENSOR CALIBRATION
# ============================================================================

# IMU (Inertial Measurement Unit) offsets
# Set to 0 initially, adjust after calibration
IMU_PITCH_OFFSET = 0.0
IMU_ROLL_OFFSET = 0.0

# Compass declination (degrees, varies by location)
# Stanford, CA: ~12.5 degrees
COMPASS_DECLINATION = 12.5

# Barometer altitude offset (meters)
BAROMETER_OFFSET = 0.0

# ============================================================================
# LOGGING
# ============================================================================

LOG_FILE = 'logs/drone_flight.log'
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR

# What to log
LOG_ATTITUDE = True
LOG_ALTITUDE = True
LOG_BATTERY = True
LOG_GPS = True
LOG_MOTOR_OUTPUTS = True

# Log frequency (Hz)
LOG_FREQUENCY = 10  # Log 10 times per second

# ============================================================================
# TESTING PARAMETERS
# ============================================================================

# Motor test duration (seconds)
MOTOR_TEST_DURATION = 3.0

# Motor test PWM increment per step
MOTOR_TEST_INCREMENT = 10

# Sensor test duration (seconds)
SENSOR_TEST_DURATION = 5.0

# ============================================================================
# COMMUNICATION
# ============================================================================

# Heartbeat timeout (seconds)
HEARTBEAT_TIMEOUT = 10

# Connection retry attempts
CONNECTION_RETRIES = 3

# Message update rate (Hz)
MESSAGE_RATE = 50

# ============================================================================
# ADVANCED PARAMETERS (Don't change unless you know what you're doing)
# ============================================================================

# Anti-windup limits for integral term
INTEGRAL_MAX = 100.0
INTEGRAL_MIN = -100.0

# Derivative filter (reduces noise)
DERIVATIVE_FILTER = 0.1

# Minimum time between updates (prevent control instability)
MIN_UPDATE_TIME = 0.001  # 1 millisecond

# Motor mixing algorithm
# Standard X quadcopter configuration
MOTOR_MIX = [
    [1.0, 1.0, 1.0, -1.0],   # Motor 1: pitch-, roll+, yaw+
    [1.0, 1.0, -1.0, 1.0],   # Motor 2: pitch+, roll+, yaw-
    [1.0, -1.0, 1.0, 1.0],   # Motor 3: pitch-, roll-, yaw-
    [1.0, -1.0, -1.0, -1.0]  # Motor 4: pitch+, roll-, yaw+
]
