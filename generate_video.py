#!/usr/bin/env python3
"""
Script-to-Video Generator
Converts text scripts into slideshow videos with AI narration and background music
"""

import os
import json
import argparse
import sys
from pathlib import Path
import requests
from datetime import datetime
import subprocess
import tempfile
import shutil

try:
    from diffusers import StableDiffusionPipeline
    import torch
    from PIL import Image
    import librosa
    import soundfile as sf
    from pydub import AudioSegment
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)

class VideoGenerator:
    def __init__(self, config_file="config.json"):
        """Initialize video generator with config"""
        self.config = self.load_config(config_file)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.temp_dir = tempfile.mkdtemp()
        print(f"[INFO] Using device: {self.device}")
        print(f"[INFO] Temp directory: {self.temp_dir}")
        
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            return {
                "output_resolution": [1920, 1080],
                "fps": 24,
                "slide_duration": 5,
                "model_name": "runwayml/stable-diffusion-v1-5",
                "tts_model": "espeak-ng",
                "background_music_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
            }
    
    def load_script(self, script_file):
        """Load and parse script file"""
        if not os.path.exists(script_file):
            print(f"[ERROR] Script file not found: {script_file}")
            sys.exit(1)
        
        with open(script_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Split script into scenes (separated by blank lines or ---)
        scenes = []
        current_scene = []
        
        for line in content.split('\n'):
            if line.strip() == '' or line.strip().startswith('---'):
                if current_scene:
                    scenes.append('\n'.join(current_scene))
                    current_scene = []
            else:
                current_scene.append(line)
        
        if current_scene:
            scenes.append('\n'.join(current_scene))
        
        return [s.strip() for s in scenes if s.strip()]
    
    def generate_image(self, prompt):
        """Generate image from text prompt using Stable Diffusion"""
        try:
            print(f"[INFO] Generating image for prompt: {prompt[:50]}...")
            
            pipe = StableDiffusionPipeline.from_pretrained(
                self.config["model_name"],
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None
            )
            pipe = pipe.to(self.device)
            
            with torch.no_grad():
                image = pipe(prompt, num_inference_steps=20, guidance_scale=7.5).images[0]
            
            return image
        except Exception as e:
            print(f"[ERROR] Failed to generate image: {e}")
            # Return a placeholder image
            return Image.new('RGB', tuple(self.config["output_resolution"]), color='blue')
    
    def generate_narration(self, text, output_file):
        """Generate text-to-speech narration"""
        try:
            print(f"[INFO] Generating narration: {text[:50]}...")
            
            # Using espeak-ng for free TTS
            cmd = f'espeak-ng -w "{output_file}" "{text}"'
            os.system(cmd)
            
            if os.path.exists(output_file):
                print(f"[INFO] Narration saved: {output_file}")
                return True
            else:
                print("[WARNING] Narration generation failed, using silent audio")
                return False
        except Exception as e:
            print(f"[ERROR] TTS generation failed: {e}")
            return False
    
    def download_background_music(self):
        """Download royalty-free background music"""
        try:
            print("[INFO] Downloading background music...")
            music_url = self.config.get("background_music_url")
            music_file = os.path.join(self.temp_dir, "background_music.mp3")
            
            response = requests.get(music_url, timeout=10)
            with open(music_file, 'wb') as f:
                f.write(response.content)
            
            print(f"[INFO] Background music downloaded: {music_file}")
            return music_file
        except Exception as e:
            print(f"[WARNING] Failed to download background music: {e}")
            return None
    
    def create_silent_audio(self, duration_seconds):
        """Create silent audio track"""
        sample_rate = 44100
        silent_audio = np.zeros((int(sample_rate * duration_seconds),), dtype=np.float32)
        return silent_audio, sample_rate
    
    def mix_audio(self, narration_file, background_music_file, output_file, video_duration):
        """Mix narration and background music"""
        try:
            print("[INFO] Mixing audio tracks...")
            
            # Load narration
            if narration_file and os.path.exists(narration_file):
                narration = AudioSegment.from_file(narration_file)
            else:
                narration = AudioSegment.silent(duration=int(video_duration * 1000))
            
            # Load background music
            if background_music_file and os.path.exists(background_music_file):
                background = AudioSegment.from_file(background_music_file)
                # Loop background music if needed
                while len(background) < len(narration):
                    background = background + background
                background = background[:len(narration)]
            else:
                background = AudioSegment.silent(duration=len(narration))
            
            # Reduce background music volume
            background = background - 15
            
            # Mix audio
            mixed = narration.overlay(background)
            mixed.export(output_file, format="mp3")
            
            print(f"[INFO] Audio mixed: {output_file}")
            return True
        except Exception as e:
            print(f"[ERROR] Audio mixing failed: {e}")
            return False
    
    def create_video(self, images, narration_file, background_music_file, output_file):
        """Create video from images, narration, and background music"""
        try:
            print("[INFO] Creating video...")
            
            # Video properties
            width, height = self.config["output_resolution"]
            fps = self.config["fps"]
            slide_duration = self.config["slide_duration"]
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
            
            # Write frames
            total_frames = 0
            for img in images:
                # Resize image to match resolution
                img_resized = img.resize((width, height), Image.Resampling.LANCZOS)
                frame = cv2.cvtColor(np.array(img_resized), cv2.COLOR_RGB2BGR)
                
                # Write frame multiple times based on slide duration
                for _ in range(int(fps * slide_duration)):
                    out.write(frame)
                    total_frames += 1
            
            out.release()
            video_duration = total_frames / fps
            print(f"[INFO] Video created: {output_file} ({video_duration:.2f}s)")
            
            # Add audio to video
            temp_video = os.path.join(self.temp_dir, "temp_video.mp4")
            os.rename(output_file, temp_video)
            
            # Mix audio
            audio_file = os.path.join(self.temp_dir, "mixed_audio.mp3")
            self.mix_audio(narration_file, background_music_file, audio_file, video_duration)
            
            # Combine video and audio using ffmpeg
            cmd = f'ffmpeg -i "{temp_video}" -i "{audio_file}" -c:v copy -c:a aac -shortest "{output_file}" -y'
            os.system(cmd)
            
            print(f"[INFO] Final video saved: {output_file}")
            return True
        except Exception as e:
            print(f"[ERROR] Video creation failed: {e}")
            return False
    
    def generate(self, script_file, output_file):
        """Main generation pipeline"""
        try:
            print(f"\n[START] Video generation started at {datetime.now()}")
            print(f"[INFO] Script: {script_file}")
            print(f"[INFO] Output: {output_file}")
            
            # Load script
            scenes = self.load_script(script_file)
            print(f"[INFO] Loaded {len(scenes)} scenes")
            
            # Generate images
            images = []
            narration_files = []
            
            for i, scene in enumerate(scenes):
                print(f"\n[SCENE {i+1}/{len(scenes)}]")
                
                # Generate image
                image = self.generate_image(scene)
                images.append(image)
                
                # Generate narration
                narration_file = os.path.join(self.temp_dir, f"narration_{i}.wav")
                self.generate_narration(scene, narration_file)
                narration_files.append(narration_file)
            
            # Download background music
            background_music = self.download_background_music()
            
            # Combine all narrations
            combined_narration = os.path.join(self.temp_dir, "combined_narration.wav")
            try:
                combined_audio = AudioSegment.silent(duration=0)
                for narration_file in narration_files:
                    if os.path.exists(narration_file):
                        audio = AudioSegment.from_file(narration_file)
                        combined_audio = combined_audio + audio
                if len(combined_audio) > 0:
                    combined_audio.export(combined_narration, format="wav")
            except:
                combined_narration = None
            
            # Create video
            self.create_video(images, combined_narration, background_music, output_file)
            
            print(f"\n[SUCCESS] Video generation completed!")
            print(f"[OUTPUT] {output_file}")
            
            # Cleanup
            shutil.rmtree(self.temp_dir)
            
        except Exception as e:
            print(f"[ERROR] Generation failed: {e}")
            shutil.rmtree(self.temp_dir)
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Convert text scripts to video with AI narration and background music"
    )
    parser.add_argument('--script', required=True, help='Path to input script file')
    parser.add_argument('--output', required=True, help='Path to output video file')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    
    args = parser.parse_args()
    
    generator = VideoGenerator(args.config)
    generator.generate(args.script, args.output)

if __name__ == "__main__":
    main()