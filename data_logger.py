"""
Flight Data Logger
Records drone telemetry, observations, and GPS-tagged data during flights

Captures:
- Sensor readings (IMU, GPS, altitude, battery)
- Flight telemetry (state, control outputs)
- Video/image observations with GPS tags
- Mission events
"""

import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import time

logger = logging.getLogger(__name__)


@dataclass
class FlightRecord:
    """Single flight telemetry record"""
    timestamp: float
    epoch_time: str
    
    # Position
    gps_lat: float
    gps_lon: float
    altitude: float
    gps_satellites: int
    
    # Attitude
    pitch: float
    roll: float
    yaw: float
    
    # Performance
    battery_voltage: float
    motor_1_pwm: int
    motor_2_pwm: int
    motor_3_pwm: int
    motor_4_pwm: int
    
    # Mission
    mission_state: str
    waypoint_index: int
    distance_to_waypoint: float


@dataclass
class Observation:
    """Single observation (image + analysis metadata)"""
    observation_id: str
    timestamp: float
    gps_lat: float
    gps_lon: float
    altitude: float
    
    # Observation data
    image_filename: str
    description: str = ""
    object_class: str = ""  # Building, bridge, etc
    confidence: float = 0.0


class FlightDataLogger:
    """
    Logs all flight data to structured files
    Creates CSV for telemetry, JSON for observations
    """
    
    def __init__(self, flight_name: str = None):
        """
        Initialize flight logger
        
        Args:
            flight_name: Custom flight identifier. If None, uses timestamp.
        """
        self.flight_name = flight_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.flight_dir = Path(f"flights/{self.flight_name}")
        self.flight_dir.mkdir(parents=True, exist_ok=True)
        
        # Flight metadata
        self.start_time = time.time()
        self.flight_data: List[FlightRecord] = []
        self.observations: List[Observation] = []
        
        # CSV file for telemetry
        self.telemetry_file = self.flight_dir / "telemetry.csv"
        self.observations_file = self.flight_dir / "observations.json"
        self.metadata_file = self.flight_dir / "metadata.json"
        
        logger.info(f"Flight logger initialized: {self.flight_dir}")
        self._write_header()
    
    def _write_header(self):
        """Write CSV header"""
        if FlightRecord.__dataclass_fields__:
            headers = list(FlightRecord.__dataclass_fields__.keys())
            with open(self.telemetry_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            logger.info(f"Telemetry file created: {self.telemetry_file}")
    
    def log_telemetry(self, record: FlightRecord):
        """
        Log single telemetry record
        
        Args:
            record: FlightRecord with sensor data
        """
        self.flight_data.append(record)
        
        # Write to CSV immediately (append mode)
        with open(self.telemetry_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(record).keys())
            writer.writerow(asdict(record))
    
    def log_observation(self, observation: Observation):
        """
        Log observation (image + metadata)
        
        Args:
            observation: Observation object with GPS tag and analysis
        """
        self.observations.append(observation)
        logger.info(f"Observation logged: {observation.observation_id} at ({observation.gps_lat:.6f}, {observation.gps_lon:.6f})")
    
    def add_observation_image(self, image_data, observation_id: str):
        """
        Save observation image to flight directory
        
        Args:
            image_data: Image bytes or file path
            observation_id: Unique ID for this observation
        """
        image_path = self.flight_dir / f"obs_{observation_id}.jpg"
        
        if isinstance(image_data, str):
            # Copy file
            import shutil
            shutil.copy(image_data, image_path)
        else:
            # Write binary data
            with open(image_path, 'wb') as f:
                f.write(image_data)
        
        logger.info(f"Observation image saved: {image_path}")
    
    def finalize_flight(self, success: bool = True):
        """
        Finalize flight log
        Writes observations JSON and metadata
        
        Args:
            success: Whether flight completed successfully
        """
        flight_duration = time.time() - self.start_time
        
        # Write observations
        obs_list = [asdict(obs) for obs in self.observations]
        with open(self.observations_file, 'w') as f:
            json.dump(obs_list, f, indent=2)
        
        # Write metadata
        metadata = {
            'flight_name': self.flight_name,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
            'duration_seconds': flight_duration,
            'success': success,
            'total_telemetry_records': len(self.flight_data),
            'total_observations': len(self.observations),
            'telemetry_file': str(self.telemetry_file),
            'observations_file': str(self.observations_file),
            'images_directory': str(self.flight_dir)
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Flight finalized: {flight_duration:.1f}s, {len(self.observations)} observations")
        logger.info(f"Flight data saved to: {self.flight_dir}")
    
    def get_flight_summary(self) -> Dict[str, Any]:
        """Get flight summary statistics"""
        if not self.flight_data:
            return {}
        
        altitudes = [r.altitude for r in self.flight_data]
        batteries = [r.battery_voltage for r in self.flight_data]
        
        summary = {
            'flight_name': self.flight_name,
            'num_records': len(self.flight_data),
            'duration': self.flight_data[-1].timestamp - self.flight_data[0].timestamp,
            'max_altitude': max(altitudes),
            'avg_altitude': sum(altitudes) / len(altitudes),
            'min_battery': min(batteries),
            'num_observations': len(self.observations),
            'observations': [
                {
                    'id': obs.observation_id,
                    'location': f"({obs.gps_lat:.6f}, {obs.gps_lon:.6f})",
                    'altitude': f"{obs.altitude:.1f}m",
                    'class': obs.object_class,
                    'confidence': f"{obs.confidence:.1%}"
                }
                for obs in self.observations
            ]
        }
        
        return summary


class ObservationCollector:
    """
    Collects and manages observations during autonomous flight
    Integrates with flight logger
    """
    
    def __init__(self, flight_logger: FlightDataLogger):
        """
        Initialize observation collector
        
        Args:
            flight_logger: FlightDataLogger instance
        """
        self.logger = flight_logger
        self.observation_count = 0
    
    def capture_observation(self, image_path: str, gps_lat: float, gps_lon: float,
                           altitude: float, object_class: str = "unknown") -> Observation:
        """
        Capture and log an observation
        
        Args:
            image_path: Path to image file
            gps_lat, gps_lon: GPS coordinates
            altitude: Altitude in meters
            object_class: Classification of observed object
        
        Returns:
            Observation object
        """
        self.observation_count += 1
        obs_id = f"{self.observation_count:04d}"
        timestamp = time.time()
        
        observation = Observation(
            observation_id=obs_id,
            timestamp=timestamp,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            altitude=altitude,
            image_filename=image_path,
            object_class=object_class
        )
        
        self.logger.log_observation(observation)
        self.logger.add_observation_image(image_path, obs_id)
        
        logger.info(f"Captured observation {obs_id}: {object_class} at {gps_lat:.6f}, {gps_lon:.6f}")
        
        return observation
    
    def batch_capture_observations(self, observations_data: List[Dict]) -> List[Observation]:
        """
        Capture multiple observations at once
        
        Args:
            observations_data: List of dicts with observation info
        
        Returns:
            List of Observation objects
        """
        observations = []
        for obs_data in observations_data:
            obs = self.capture_observation(
                image_path=obs_data.get('image_path'),
                gps_lat=obs_data.get('gps_lat'),
                gps_lon=obs_data.get('gps_lon'),
                altitude=obs_data.get('altitude'),
                object_class=obs_data.get('object_class', 'unknown')
            )
            observations.append(obs)
        
        return observations


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create logger
    logger_obj = FlightDataLogger("example_flight")
    collector = ObservationCollector(logger_obj)
    
    # Simulate flight data
    logger.info("Simulating flight...")
    
    for i in range(10):
        record = FlightRecord(
            timestamp=i,
            epoch_time=datetime.now().isoformat(),
            gps_lat=37.4274 + i*0.0001,
            gps_lon=-122.1695 + i*0.0001,
            altitude=10.0 + i*0.5,
            gps_satellites=12,
            pitch=0.0,
            roll=0.0,
            yaw=0.0,
            battery_voltage=11.8 - i*0.05,
            motor_1_pwm=1500,
            motor_2_pwm=1500,
            motor_3_pwm=1500,
            motor_4_pwm=1500,
            mission_state='NAVIGATING',
            waypoint_index=0,
            distance_to_waypoint=50.0 - i*5
        )
        logger_obj.log_telemetry(record)
        time.sleep(0.1)
    
    # Log observations
    obs = Observation(
        observation_id="0001",
        timestamp=time.time(),
        gps_lat=37.4275,
        gps_lon=-122.1695,
        altitude=15.0,
        image_filename="observation_0001.jpg",
        object_class="building",
        confidence=0.95
    )
    logger_obj.log_observation(obs)
    
    # Finalize
    summary = logger_obj.get_flight_summary()
    logger.info(f"Flight summary: {summary}")
    logger_obj.finalize_flight(success=True)
