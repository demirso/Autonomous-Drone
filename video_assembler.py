"""
Video Assembly Script
Automatically combines video clips, voiceover, and subtitles into final video

Usage:
    python video_assembler.py --voiceover audio.m4a --output final_video.mp4
    
Requires:
    - Video clips in clips/ folder
    - Voiceover audio file
    - Subtitles already synced (drone_subtitles.srt)
"""

import argparse
import logging
from pathlib import Path
import subprocess
import json
from datetime import timedelta

try:
    from moviepy.editor import (
        VideoFileClip, concatenate_videoclips,
        AudioFileClip, CompositeAudioClip, CompositeVideoClip,
        TextClip, ColorClip
    )
    import srt
except ImportError:
    print("Installing required packages...")
    subprocess.run(["pip", "install", "moviepy", "srt"], check=True)
    from moviepy.editor import (
        VideoFileClip, concatenate_videoclips,
        AudioFileClip, CompositeAudioClip, CompositeVideoClip,
        TextClip, ColorClip
    )
    import srt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoAssembler:
    """
    Assembles drone video with voiceover and subtitles
    """
    
    def __init__(self, clips_dir: str = "clips", subtitles_file: str = "drone_subtitles.srt"):
        """
        Initialize video assembler
        
        Args:
            clips_dir: Directory containing video clips
            subtitles_file: Path to SRT subtitle file
        """
        self.clips_dir = Path(clips_dir)
        self.subtitles_file = Path(subtitles_file)
        
        if not self.clips_dir.exists():
            logger.error(f"Clips directory not found: {self.clips_dir}")
            raise FileNotFoundError(f"Directory {self.clips_dir} not found")
        
        if not self.subtitles_file.exists():
            logger.error(f"Subtitle file not found: {self.subtitles_file}")
            raise FileNotFoundError(f"File {self.subtitles_file} not found")
        
        # Load subtitles
        self.subtitles = self._load_subtitles()
        logger.info(f"Loaded {len(self.subtitles)} subtitle chunks")
    
    def _load_subtitles(self) -> list:
        """Load SRT subtitle file"""
        with open(self.subtitles_file, 'r') as f:
            subtitles = list(srt.parse(f.read()))
        return subtitles
    
    def _get_video_clips(self) -> list:
        """Get all video clips from clips directory"""
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
        clips = []
        
        # Get all video files, sorted by name
        for ext in video_extensions:
            clips.extend(sorted(self.clips_dir.glob(f"*{ext}")))
        
        if not clips:
            logger.error(f"No video clips found in {self.clips_dir}")
            raise FileNotFoundError(f"No videos in {self.clips_dir}")
        
        logger.info(f"Found {len(clips)} video clips:")
        for clip in clips:
            logger.info(f"  - {clip.name}")
        
        return clips
    
    def _concatenate_clips(self) -> VideoFileClip:
        """Concatenate all video clips"""
        logger.info("Concatenating video clips...")
        
        clips = self._get_video_clips()
        video_clips = []
        
        for clip_path in clips:
            try:
                clip = VideoFileClip(str(clip_path))
                video_clips.append(clip)
                logger.info(f"  Loaded: {clip_path.name} ({clip.duration:.1f}s)")
            except Exception as e:
                logger.error(f"  Failed to load {clip_path}: {e}")
        
        if not video_clips:
            raise ValueError("No valid video clips could be loaded")
        
        # Concatenate
        final_clip = concatenate_videoclips(video_clips)
        logger.info(f"Concatenated video duration: {final_clip.duration:.1f}s")
        
        return final_clip
    
    def _add_voiceover(self, video_clip: VideoFileClip, voiceover_path: str) -> VideoFileClip:
        """Add voiceover audio to video"""
        logger.info(f"Adding voiceover: {voiceover_path}")
        
        voiceover = AudioFileClip(voiceover_path)
        logger.info(f"Voiceover duration: {voiceover.duration:.1f}s")
        
        # Get video audio (if exists)
        if video_clip.audio is not None:
            # Mix voiceover with video audio (voiceover louder)
            composite_audio = CompositeAudioClip([
                video_clip.audio.volumex(0.3),  # Video audio at 30%
                voiceover.volumex(1.0)  # Voiceover at 100%
            ])
        else:
            # No video audio, just use voiceover
            composite_audio = voiceover
        
        # Set audio to video
        final_clip = video_clip.set_audio(composite_audio)
        
        return final_clip
    
    def _create_subtitle_clips(self, video_duration: float) -> list:
        """Create text clips for each subtitle"""
        logger.info("Creating subtitle text clips...")
        
        subtitle_clips = []
        
        for subtitle in self.subtitles:
            # Get timing
            start_time = subtitle.start.total_seconds()
            end_time = subtitle.end.total_seconds()
            duration = end_time - start_time
            
            # Skip if beyond video duration
            if start_time > video_duration:
                continue
            
            # Adjust end time if beyond video
            if end_time > video_duration:
                duration = video_duration - start_time
            
            # Create text clip
            try:
                txt_clip = TextClip(
                    txt=subtitle.content,
                    fontsize=48,
                    font='Arial',
                    color='white',
                    method='caption',  # Word wrap
                    size=(1080, 200)  # Width, height for wrapping
                )
                
                # Position at bottom center
                txt_clip = txt_clip.set_position(
                    ('center', 'bottom')
                ).set_duration(duration).set_start(start_time)
                
                # Add background for readability
                bg_clip = ColorClip(
                    size=(txt_clip.w + 20, txt_clip.h + 20),
                    color=(0, 0, 0)
                ).set_opacity(0.7).set_duration(duration).set_start(start_time).set_position(
                    ('center', 'bottom')
                )
                
                subtitle_clips.append(bg_clip)
                subtitle_clips.append(txt_clip)
                
            except Exception as e:
                logger.warning(f"Failed to create subtitle clip: {e}")
        
        logger.info(f"Created {len(subtitle_clips) // 2} subtitle text clips")
        return subtitle_clips
    
    def _add_subtitles(self, video_clip: VideoFileClip) -> VideoFileClip:
        """Add subtitles to video"""
        logger.info("Adding subtitles...")
        
        # Create subtitle clips
        subtitle_clips = self._create_subtitle_clips(video_clip.duration)
        
        if subtitle_clips:
            # Composite video with subtitles
            final_clip = CompositeVideoClip(
                [video_clip] + subtitle_clips
            )
        else:
            final_clip = video_clip
        
        return final_clip
    
    def assemble_video(self, voiceover_path: str, output_path: str = "final_video.mp4") -> bool:
        """
        Assemble complete video with voiceover and subtitles
        
        Args:
            voiceover_path: Path to voiceover audio file
            output_path: Output video file path
        
        Returns:
            True if successful
        """
        try:
            logger.info("\n" + "=" * 60)
            logger.info("VIDEO ASSEMBLY PROCESS")
            logger.info("=" * 60)
            
            voiceover_path = Path(voiceover_path)
            if not voiceover_path.exists():
                logger.error(f"Voiceover file not found: {voiceover_path}")
                return False
            
            # Step 1: Concatenate clips
            logger.info("\n[1/4] Concatenating video clips...")
            video = self._concatenate_clips()
            
            # Step 2: Add voiceover
            logger.info("\n[2/4] Adding voiceover audio...")
            video = self._add_voiceover(video, str(voiceover_path))
            
            # Step 3: Add subtitles
            logger.info("\n[3/4] Adding subtitles...")
            video = self._add_subtitles(video)
            
            # Step 4: Export
            logger.info(f"\n[4/4] Exporting video to {output_path}...")
            logger.info("This may take several minutes...")
            
            video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=30,
                verbose=False,
                logger=None  # Suppress moviepy output
            )
            
            logger.info("\n" + "=" * 60)
            logger.info("✓ VIDEO ASSEMBLY COMPLETE")
            logger.info(f"Output: {output_path}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Video assembly failed: {e}", exc_info=True)
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Autonomous Drone Video Assembler"
    )
    
    parser.add_argument(
        '--voiceover',
        type=str,
        required=True,
        help='Path to voiceover audio file (m4a, mp3, wav, etc)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='drone_project_final.mp4',
        help='Output video file path'
    )
    
    parser.add_argument(
        '--clips-dir',
        type=str,
        default='clips',
        help='Directory containing video clips'
    )
    
    parser.add_argument(
        '--subtitles',
        type=str,
        default='drone_subtitles.srt',
        help='Path to SRT subtitle file'
    )
    
    args = parser.parse_args()
    
    logger.info("Autonomous Drone Video Assembler")
    logger.info("=" * 60)
    
    try:
        assembler = VideoAssembler(
            clips_dir=args.clips_dir,
            subtitles_file=args.subtitles
        )
        
        success = assembler.assemble_video(
            voiceover_path=args.voiceover,
            output_path=args.output
        )
        
        if success:
            logger.info("\n✓ Video ready for submission!")
            logger.info(f"File: {args.output}")
        else:
            logger.error("Video assembly failed")
            return 1
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
