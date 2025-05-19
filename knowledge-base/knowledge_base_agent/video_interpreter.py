import base64
import logging
import tempfile
import os
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from knowledge_base_agent.exceptions import VisionModelError
from knowledge_base_agent.http_client import HTTPClient

async def extract_frames(video_path: Path, num_frames: int = 5) -> List[Path]:
    """
    Extract representative frames from a video using ffmpeg.
    
    Args:
        video_path: Path to the video file
        num_frames: Number of frames to extract (default: 5)
        
    Returns:
        List of paths to extracted frame images
    """
    try:
        # Create a temporary directory to store the frames
        temp_dir = Path(tempfile.mkdtemp())
        frame_pattern = temp_dir / "frame_%03d.jpg"
        
        # Calculate the frame extraction interval based on video duration
        # First, get video duration using ffprobe
        duration_cmd = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            str(video_path)
        ]
        
        duration_result = subprocess.run(
            duration_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if duration_result.returncode != 0:
            logging.error(f"Failed to get video duration: {duration_result.stderr}")
            # Fallback to fixed interval extraction
            interval = 1.0
        else:
            try:
                duration = float(duration_result.stdout.strip())
                # Extract frames at regular intervals across the video
                # Ensure at least 1 second between frames
                interval = max(1.0, duration / (num_frames + 1))
            except (ValueError, ZeroDivisionError):
                logging.error("Invalid duration value, using default interval")
                interval = 1.0
        
        # Extract frames at calculated intervals
        extract_cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-vframes", str(num_frames),
            "-q:v", "2",  # High quality
            str(frame_pattern)
        ]
        
        extract_result = subprocess.run(
            extract_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if extract_result.returncode != 0:
            logging.error(f"Failed to extract video frames: {extract_result.stderr}")
            return []
        
        # Get the extracted frame paths
        frames = sorted(list(temp_dir.glob("*.jpg")))
        logging.info(f"Extracted {len(frames)} frames from video {video_path}")
        return frames
        
    except Exception as e:
        logging.error(f"Error extracting frames from video {video_path}: {e}")
        return []

async def interpret_video(http_client: HTTPClient, video_path: Path, vision_model: str) -> str:
    """
    Interpret video content by extracting frames and using the vision model.
    
    Args:
        http_client: HTTP client for making requests
        video_path: Path to the video file
        vision_model: Name of the vision model to use
        
    Returns:
        String description of the video content
    """
    try:
        # Extract frames from the video
        frames = await extract_frames(video_path)
        
        if not frames:
            logging.error(f"No frames could be extracted from video {video_path}")
            return f"No frames could be extracted from the video file: {video_path.name}"
        
        # Read and encode frames
        frame_descriptions = []
        frame_images = []
        
        # Process each frame
        for i, frame_path in enumerate(frames[:5]):  # Limit to at most 5 frames
            try:
                with open(frame_path, 'rb') as f:
                    image_bytes = f.read()
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    frame_images.append(image_base64)
            except Exception as e:
                logging.error(f"Failed to read frame {frame_path}: {e}")
        
        # First, get descriptions of individual frames
        for i, image_base64 in enumerate(frame_images):
            try:
                # Prepare prompt for vision model for a single frame
                single_frame_prompt = f"Describe frame {i+1} of this video, focusing on the visible content."
                
                # Use /api/generate endpoint with image
                response = await http_client.post(
                    f"{http_client.base_url}/api/generate",
                    json={
                        "model": vision_model,
                        "prompt": single_frame_prompt,
                        "images": [image_base64],
                        "stream": False
                    }
                )
                
                if isinstance(response, dict) and "response" in response:
                    frame_desc = response["response"].strip()
                    frame_descriptions.append(f"Frame {i+1}: {frame_desc}")
                else:
                    logging.warning(f"Invalid response format from vision model for frame {i+1}")
            except Exception as e:
                logging.error(f"Failed to process frame {i+1}: {e}")
                frame_descriptions.append(f"Frame {i+1}: [Processing error]")
        
        # Now, send the first frame with a prompt that asks for an overall description
        if frame_images:
            try:
                # Use multiple frames if the model supports it, otherwise just the first frame
                frames_to_send = frame_images[:3]  # Most models have a limit on the number of images
                
                # Prepare prompt for overall video interpretation
                prompt = (
                    "This is a video. I've extracted multiple key frames from it. "
                    "Based on these frames, provide a comprehensive description of what this video is about. "
                    "Focus on the overall content, any technical concepts shown, and the main subject matter. "
                    "Describe it as a cohesive video rather than individual frames."
                )
                
                response = await http_client.post(
                    f"{http_client.base_url}/api/generate",
                    json={
                        "model": vision_model,
                        "prompt": prompt,
                        "images": frames_to_send,
                        "stream": False
                    }
                )
                
                overall_description = ""
                if isinstance(response, dict) and "response" in response:
                    overall_description = response["response"].strip()
                else:
                    logging.warning("Invalid response format from vision model for overall description")
                    overall_description = "Could not generate an overall description."
            except Exception as e:
                logging.error(f"Failed to generate overall video description: {e}")
                overall_description = "Error generating overall video description."
        else:
            overall_description = "No frames available for overall description."
        
        # Clean up temporary files
        for frame in frames:
            try:
                frame.unlink()
            except:
                pass
        try:
            frames[0].parent.rmdir()
        except:
            pass
        
        # Combine descriptions into a complete video analysis
        result = f"Video Content Analysis - {video_path.name}:\n\n"
        result += f"{overall_description}\n\n"
        
        # Add frame descriptions if meaningful
        if len(frame_descriptions) > 1:  # Only include if we have multiple frames
            result += "Key Frames Analysis:\n"
            result += "\n".join(frame_descriptions)
        
        return result

    except Exception as e:
        logging.error(f"Failed to interpret video {video_path}: {e}")
        raise VisionModelError(f"Failed to interpret video {video_path}: {e}") 