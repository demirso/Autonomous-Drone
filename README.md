# Autonomous Quadcopter Flight Controller

Custom flight control software for autonomous drone using Pixhawk 2.4.8 and Raspberry Pi 4.

**Author:** Demir Sonar
**Project:** CS 153 Autonomous Drone System  
**Status:** Early Development (Motor Control & Stabilization Phase)

---

## ⚠️ SAFETY WARNINGS

**READ BEFORE USING:**

1. **PROPELLERS OFF** - Remove all propellers before testing motor control
2. **BATTERY DISCONNECTED** - During ESC calibration, battery must be unplugged
3. **SUPERVISED TESTING ONLY** - Never run autonomous code unattended
4. **OPEN SPACE REQUIRED** - Test in large open area away from people/objects
5. **EMERGENCY STOP** - Have ability to cut power immediately if needed
6. **PID TUNING REQUIRED** - Default gains are conservative, will need adjustment
7. **NOT PRODUCTION READY** - This is research/educational code, not for commercial use

---

## System Overview

### Hardware
- **Flight Controller:** Pixhawk 2.4.8 (STM32F427, 168MHz)
- **Compute:** Raspberry Pi 4 (2GB)
- **Motors:** 4× Brushless motors via ESCs
- **Sensors:** Built-in IMU (gyro, accel, mag), barometer, GPS
- **Battery:** 3S LiPo (11.1V)

### Software Components

```
├── flight_controller.py       # Main flight control loop
├── stabilization_controller.py # PID stabilization
├── config.py                   # Configuration parameters
└── autonomous_mission.py       # Waypoint navigation (future)
```

---

## Installation

### 1. Install Dependencies on Raspberry Pi

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3 and pip
sudo apt-get install -y python3 python3-pip

# Install MAVProxy and PyMAVLink (for Pixhawk communication)
pip3 install pymavlink

# Clone this repository
git clone https://github.com/[your-username]/autonomous-quadcopter.git
cd autonomous-quadcopter
```

### 2. Hardware Setup

**USB Connection:**
- Connect Pixhawk to Raspberry Pi via USB cable
- Pixhawk will appear as `/dev/ttyUSB0`

**Motor Connections:**
- Motor 1 (Front Right) → Pixhawk PWM channel 1
- Motor 2 (Rear Left) → Pixhawk PWM channel 2
- Motor 3 (Front Left) → Pixhawk PWM channel 3
- Motor 4 (Rear Right) → Pixhawk PWM channel 4

**GPS Connection:**
- GPS TX → Pixhawk GPS RX
- GPS RX → Pixhawk GPS TX
- GND → GND
- VCC → 5V

### 3. ESC Calibration (ONE TIME ONLY)

```bash
# Run ESC calibration
python3 flight_controller.py --calibrate-esc

# IMPORTANT:
# 1. Disconnect battery
# 2. Run script (will set throttle to MAX)
# 3. Connect battery when prompted
# 4. Wait for beeping pattern
# 5. Script will set throttle to MIN
# 6. Disconnect battery
# 7. Reconnect and test
```

---

## Usage

### Basic Motor Test (PROPELLERS REMOVED)

```bash
python3 flight_controller.py --test-motors
```

This will:
1. Gradually increase motor throttle
2. Display PWM values
3. Return to safe state

**ENSURE PROPELLERS ARE REMOVED BEFORE RUNNING THIS**

### Sensor Test

```bash
python3 flight_controller.py --test-sensors
```

Reads and displays:
- IMU attitude (pitch, roll, yaw)
- Altitude
- Battery voltage
- GPS position

### Code Examples

#### Reading Sensor Data

```python
from flight_controller import FlightController

fc = FlightController()

# Read attitude
pitch, roll, yaw = fc.sensors.read_attitude()
print(f"Drone orientation: {pitch}, {roll}, {yaw}")

# Read altitude
alt = fc.sensors.read_altitude()
print(f"Altitude: {alt}m")

fc.shutdown()
```

#### Motor Control

```python
from flight_controller import FlightController

fc = FlightController()

# Set all motors to 1100 PWM
fc.motors.set_motor_all(1100)

# Set individual motor
fc.motors.set_motor(1, 1200)  # Motor 1 to 1200 PWM

# Disarm (safe state)
fc.motors.disarm_motors()

fc.shutdown()
```

#### Stabilization Control

```python
from stabilization_controller import StabilizationController

stab = StabilizationController()

# Simulate current drone attitude
pitch = 0.05  # Tilted forward slightly
roll = 0.0
yaw = 0.0
throttle = 0  # 0 = hover, -100 = descent, +100 = climb

# Calculate motor outputs
motors = stab.calculate_motor_outputs(pitch, roll, yaw, throttle)
print(f"Motor PWM: {motors}")
# Output: [Motor1_PWM, Motor2_PWM, Motor3_PWM, Motor4_PWM]
```

---

## Code Architecture

### FlightController (Main Module)

**Responsibilities:**
- Connection to Pixhawk via USB
- Heartbeat management
- Orchestration of motors and sensors

**Key Methods:**
- `test_motors(duration)` - Motor response test
- `test_sensors(duration)` - Sensor data readout
- `shutdown()` - Safe shutdown

### MotorController (Motor Output)

**PWM Range:**
- Minimum: 1000 (0% throttle)
- Neutral: 1500 (hover point - ESTIMATE)
- Maximum: 2000 (100% throttle)

**Key Methods:**
- `set_motor(channel, pwm)` - Single motor control
- `set_motor_all(pwm)` - All motors to same value
- `calibrate_esc()` - ESC calibration sequence
- `disarm_motors()` - Safe shutdown

### SensorReader (Input)

**Available Readings:**
- Attitude (pitch, roll, yaw from IMU)
- Altitude (from barometer)
- Battery voltage
- GPS (position, satellite count)

**Key Methods:**
- `read_attitude()` - Returns (pitch, roll, yaw)
- `read_altitude()` - Returns altitude in meters
- `read_battery()` - Returns voltage
- `read_gps()` - Returns (lat, lon, alt, sats)

### StabilizationController (Flight Control)

**How it Works:**
1. Reads current attitude (pitch, roll, yaw)
2. Compares to desired attitude (setpoint)
3. Calculates error for each axis
4. PID controllers generate correction signals
5. Corrections applied to motors for stabilization

**PID Loop:**
```
Error = Target - Current
Output = Kp*Error + Ki*∫Error + Kd*dError/dt
```

**Key Methods:**
- `calculate_motor_outputs(pitch, roll, yaw, throttle)` - Returns 4 motor PWM values
- `set_target_attitude(pitch, roll, yaw)` - Set desired orientation
- `tune_gains(controller, kp, ki, kd)` - Adjust PID tuning

---

## PID Tuning Guide

### Current Tuning Parameters

```
Pitch PID:  Kp=1.5, Ki=0.1, Kd=0.8
Roll PID:   Kp=1.5, Ki=0.1, Kd=0.8
Yaw PID:    Kp=2.0, Ki=0.05, Kd=0.5
```

**These are conservative starting values. They will likely need adjustment.**

### Tuning Procedure

1. **Start with Proportional Only** (Ki=0, Kd=0)
   - Increase Kp until response is quick
   - Stop when oscillation starts
   
2. **Add Derivative** (Kd > 0)
   - Reduces oscillation
   - Increases stability
   
3. **Add Integral** (Ki > 0)
   - Eliminates steady-state error
   - Use sparingly to avoid windup

4. **Real-World Testing**
   - Every drone is slightly different
   - Tune in calm weather conditions
   - Make small adjustments (10-20% at a time)

### Tuning Tools

```python
# Adjust gains during testing
stab.tune_gains('pitch', kp=1.6, ki=0.1, kd=0.8)
```

---

## Testing Checklist

Before flying:

- [ ] Pixhawk connected via USB
- [ ] All motors spin freely without propellers
- [ ] Battery voltage reads correctly
- [ ] GPS has lock (4+ satellites)
- [ ] IMU sensor values reasonable
- [ ] ESCs calibrated
- [ ] Propellers mounted correctly
- [ ] Vibration dampers installed
- [ ] All connections soldered and secure

---

## Troubleshooting

### Problem: Cannot connect to Pixhawk

```
Error: "Failed to connect to Pixhawk"
Solution:
1. Check USB cable connection
2. Verify /dev/ttyUSB0 exists: ls /dev/ttyUSB*
3. Check permissions: sudo chmod 666 /dev/ttyUSB0
4. Ensure Pixhawk is powered
```

### Problem: Motors don't respond

```
Error: Motor PWM not changing
Solution:
1. Verify ESCs are armed (you should hear beep)
2. Check PWM values are in range (1000-2000)
3. Ensure PWM channel is correct (1-4)
4. Check servo connectors are seated
```

### Problem: Sensors reading zero

```
Error: Attitude/altitude always 0
Solution:
1. Check Pixhawk power (red LED should be on)
2. Calibrate compass: Q is in plane, mag not nearby
3. Level drone and hold still for IMU calibration
4. Check sensor connections
```

---

## Project Timeline

**Phase 1: Motor Control (Current) ✓**
- [x] Basic motor control
- [x] ESC calibration
- [x] Motor testing

**Phase 2: Flight Stabilization (Current)**
- [ ] PID tuning and testing
- [ ] Level flight achievement
- [ ] Attitude hold (hover in place)

**Phase 3: Altitude Control (Next)**
- [ ] Barometer calibration
- [ ] Altitude hold with throttle
- [ ] Smooth altitude changes

**Phase 4: GPS Navigation (Future)**
- [ ] Waypoint parsing
- [ ] Autonomous path following
- [ ] Mission execution

---

## File Structure

```
autonomous-quadcopter/
├── README.md                      # This file
├── flight_controller.py           # Main flight control
├── stabilization_controller.py    # PID stabilization
├── config.py                      # Configuration (TODO)
├── logs/
│   └── drone_flight.log          # Flight logs
├── tests/
│   ├── test_motors.py            # Motor tests
│   ├── test_sensors.py           # Sensor tests
│   └── test_stabilization.py     # Stabilization tests
└── docs/
    ├── HARDWARE.md               # Hardware connections
    ├── TUNING.md                 # PID tuning guide
    └── TROUBLESHOOTING.md        # Troubleshooting
```

---

## Performance Metrics

**Current Capabilities:**
- Motor control: ✓ Working
- Sensor reading: ✓ Working
- PID stabilization: ⊘ In development
- Autonomous flight: ⊘ Not yet implemented

**Next Milestones:**
1. Achieve stable level flight (no tilt)
2. Hover in place for 10+ seconds
3. Respond to attitude commands
4. Autonomous altitude hold

---

## Contributing

This is an educational project. Contributions welcome!

Before submitting:
1. Test thoroughly
2. Add comments
3. Follow PEP 8 style
4. Update README if needed

---

## License

Educational use only. Not for commercial purposes.

---

## Contact & Support

For issues or questions:
- Check troubleshooting section first
- Review flight logs in `logs/` directory
- Consult flight controller manual
- Test each component independently

---

## Acknowledgments

- Pixhawk Developer Community
- PyMAVLink Documentation
- ArduPilot Project
- CS 153 Instructors

---

**Last Updated:** 2026  
**Version:** 0.1.0 (Alpha)  
**Status:** Early Development
