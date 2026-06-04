"""
AI Analysis Module
Uses Claude API to analyze drone observations and generate intelligent reports

Performs:
- Image analysis and classification
- Pattern recognition
- Intelligent synthesis of observations
- Report generation
"""

import anthropic
import base64
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from data_logger import Observation

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """
    AI-powered analysis of drone observations
    Uses Claude API for intelligent synthesis
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize AI analyzer
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-opus-4-20250805"
        logger.info(f"AI Analyzer initialized with model: {self.model}")
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze single drone image with AI
        
        Args:
            image_path: Path to image file
        
        Returns:
            Analysis results dict
        """
        logger.info(f"Analyzing image: {image_path}")
        
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        # Determine image type
        image_type = "image/jpeg" if image_path.lower().endswith('.jpg') else "image/png"
        
        # Call Claude with vision
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Analyze this aerial drone image. Provide:
1. Main structures/objects observed
2. Building/infrastructure type (if applicable)
3. Estimated condition (good/fair/poor)
4. Notable features or damage
5. GPS observation value (1-10 scale)

Format as JSON with keys: structures, type, condition, features, value"""
                        }
                    ],
                }
            ],
        )
        
        # Parse response
        response_text = message.content[0].text
        
        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # If not valid JSON, wrap in dict
            analysis = {"raw_analysis": response_text}
        
        logger.info(f"Image analysis complete: {analysis}")
        return analysis
    
    def analyze_observation(self, observation: Observation, image_path: str = None) -> Dict[str, Any]:
        """
        Analyze single observation with AI
        
        Args:
            observation: Observation object
            image_path: Optional path to observation image
        
        Returns:
            Analysis results
        """
        analysis = {
            'observation_id': observation.observation_id,
            'location': f"({observation.gps_lat:.6f}, {observation.gps_lon:.6f})",
            'altitude': observation.altitude
        }
        
        # Analyze image if provided
        if image_path and Path(image_path).exists():
            image_analysis = self.analyze_image(image_path)
            analysis['image_analysis'] = image_analysis
        
        return analysis
    
    def synthesize_observations(self, observations: List[Observation],
                               analyses: List[Dict] = None) -> str:
        """
        Synthesize multiple observations into coherent narrative
        
        Args:
            observations: List of Observation objects
            analyses: Optional list of image analyses
        
        Returns:
            Synthesized analysis narrative
        """
        logger.info(f"Synthesizing {len(observations)} observations")
        
        # Build observation summary
        obs_text = "Drone Observations:\n"
        for i, obs in enumerate(observations):
            obs_text += f"\n{i+1}. Observation {obs.observation_id}:\n"
            obs_text += f"   Location: {obs.gps_lat:.6f}, {obs.gps_lon:.6f}\n"
            obs_text += f"   Altitude: {obs.altitude:.1f}m\n"
            obs_text += f"   Class: {obs.object_class}\n"
            
            if analyses and i < len(analyses):
                analysis = analyses[i]
                if 'image_analysis' in analysis:
                    obs_text += f"   Analysis: {json.dumps(analysis['image_analysis'], indent=2)}\n"
        
        # Ask Claude to synthesize
        prompt = f"""You are an expert drone analyst. Based on these GPS-tagged observations from an autonomous drone mission, 
provide a professional synthesis report that:

1. Summarizes key observations
2. Identifies patterns or notable features
3. Assesses overall infrastructure condition
4. Flags any areas of concern
5. Provides actionable recommendations

{obs_text}

Generate a clear, structured report suitable for stakeholders."""
        
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        synthesis = message.content[0].text
        logger.info("Observation synthesis complete")
        
        return synthesis
    
    def generate_technical_summary(self, observations: List[Observation]) -> str:
        """
        Generate technical summary with statistics
        
        Args:
            observations: List of observations
        
        Returns:
            Technical summary
        """
        # Calculate statistics
        num_obs = len(observations)
        avg_altitude = sum(o.altitude for o in observations) / num_obs if observations else 0
        
        object_classes = {}
        for obs in observations:
            object_classes[obs.object_class] = object_classes.get(obs.object_class, 0) + 1
        
        summary = f"""
TECHNICAL SUMMARY
=================

Flight Statistics:
- Total Observations: {num_obs}
- Average Altitude: {avg_altitude:.1f}m
- Coverage Area: {num_obs * 50}m² (estimated)

Observation Classification:
"""
        
        for obj_class, count in object_classes.items():
            summary += f"  - {obj_class}: {count}\n"
        
        # GPS bounds
        if observations:
            lats = [o.gps_lat for o in observations]
            lons = [o.gps_lon for o in observations]
            
            summary += f"\nGPS Coverage:\n"
            summary += f"  - Latitude range: {min(lats):.6f} to {max(lats):.6f}\n"
            summary += f"  - Longitude range: {min(lons):.6f} to {max(lons):.6f}\n"
        
        return summary
    
    def generate_geojson(self, observations: List[Observation]) -> Dict:
        """
        Generate GeoJSON from observations for mapping
        
        Args:
            observations: List of observations
        
        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        
        for obs in observations:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [obs.gps_lon, obs.gps_lat]  # GeoJSON uses [lon, lat]
                },
                "properties": {
                    "id": obs.observation_id,
                    "altitude": obs.altitude,
                    "class": obs.object_class,
                    "confidence": obs.confidence,
                    "timestamp": obs.timestamp
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        logger.info(f"Generated GeoJSON with {len(features)} features")
        return geojson


class AnalysisReport:
    """
    Generates comprehensive analysis report from observations
    """
    
    def __init__(self, flight_name: str, observations: List[Observation]):
        """
        Initialize report generator
        
        Args:
            flight_name: Flight identifier
            observations: List of observations from flight
        """
        self.flight_name = flight_name
        self.observations = observations
        self.analyzer = AIAnalyzer()
    
    def generate_full_report(self, output_path: str = None) -> Dict[str, Any]:
        """
        Generate complete analysis report
        
        Args:
            output_path: Optional path to save report
        
        Returns:
            Complete report dict
        """
        logger.info(f"Generating full report for flight: {self.flight_name}")
        
        # Technical summary
        tech_summary = self.analyzer.generate_technical_summary(self.observations)
        
        # Synthesized analysis
        synthesis = self.analyzer.synthesize_observations(self.observations)
        
        # GeoJSON for mapping
        geojson = self.analyzer.generate_geojson(self.observations)
        
        # Compile report
        report = {
            'metadata': {
                'flight_name': self.flight_name,
                'num_observations': len(self.observations),
                'generated_at': str(Path.cwd())
            },
            'technical_summary': tech_summary,
            'synthesis': synthesis,
            'geojson': geojson,
            'observations': [
                {
                    'id': obs.observation_id,
                    'location': f"({obs.gps_lat:.6f}, {obs.gps_lon:.6f})",
                    'altitude': obs.altitude,
                    'class': obs.object_class,
                    'confidence': obs.confidence
                }
                for obs in self.observations
            ]
        }
        
        # Save if path provided
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to: {output_path}")
        
        return report
    
    def generate_markdown_report(self, output_path: str = None) -> str:
        """
        Generate markdown report for easy viewing
        
        Args:
            output_path: Optional path to save markdown
        
        Returns:
            Markdown formatted report
        """
        report = self.generate_full_report()
        
        markdown = f"""# Autonomous Drone Analysis Report
## {self.flight_name}

### Summary
- **Observations**: {report['metadata']['num_observations']}
- **Generated**: {report['metadata']['generated_at']}

## Technical Summary
{report['technical_summary']}

## Analysis & Insights
{report['synthesis']}

### Observation Details
"""
        
        for obs in report['observations']:
            markdown += f"\n#### Observation {obs['id']}\n"
            markdown += f"- **Location**: {obs['location']}\n"
            markdown += f"- **Altitude**: {obs['altitude']}m\n"
            markdown += f"- **Type**: {obs['class']}\n"
            markdown += f"- **Confidence**: {obs['confidence']:.1%}\n"
        
        markdown += f"\n## GeoJSON Data\n```json\n{json.dumps(report['geojson'], indent=2)}\n```"
        
        # Save if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(markdown)
            logger.info(f"Markdown report saved to: {output_path}")
        
        return markdown


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create sample observations
    observations = [
        Observation(
            observation_id="0001",
            timestamp=0,
            gps_lat=37.4274,
            gps_lon=-122.1695,
            altitude=15.0,
            image_filename="obs_0001.jpg",
            object_class="building",
            confidence=0.95
        ),
        Observation(
            observation_id="0002",
            timestamp=1,
            gps_lat=37.4275,
            gps_lon=-122.1690,
            altitude=20.0,
            image_filename="obs_0002.jpg",
            object_class="building",
            confidence=0.92
        )
    ]
    
    # Generate report
    report_gen = AnalysisReport("example_flight", observations)
    
    # Generate markdown report
    markdown = report_gen.generate_markdown_report("example_report.md")
    logger.info("Report generated successfully")
