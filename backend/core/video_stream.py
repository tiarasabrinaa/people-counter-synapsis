# /Users/tiarasabrina/Documents/PROJECT/dashboard-people-counter/backend/core/video_stream.py

import cv2
import streamlink
from threading import Thread
import time


class VideoStreamHandler:
    def __init__(self, stream_url):
        """
        Initialize video stream handler for HLS/M3U8 streams
        
        Args:
            stream_url: HLS stream URL
        """
        self.stream_url = stream_url
        self.cap = None
        self.frame = None
        self.stopped = False
        self.frame_count = 0
    
    def start(self):
        """Start video stream in separate thread"""
        try:
            # Try streamlink first
            streams = streamlink.streams(self.stream_url)
            
            if streams:
                stream_url = streams['best'].url
                self.cap = cv2.VideoCapture(stream_url)
            else:
                # Fallback to direct OpenCV
                self.cap = cv2.VideoCapture(self.stream_url)
            
            if not self.cap.isOpened():
                print("✗ Failed to open stream")
                return False
            
            print(f"✓ Stream opened successfully")
            
            # Start frame reading thread
            Thread(target=self._update, daemon=True).start()
            
            # Wait for first frame
            time.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"✗ Error starting stream: {e}")
            
            # Try direct OpenCV as fallback
            try:
                self.cap = cv2.VideoCapture(self.stream_url)
                
                if not self.cap.isOpened():
                    return False
                
                print("✓ Stream opened with direct OpenCV")
                Thread(target=self._update, daemon=True).start()
                time.sleep(2)
                
                return True
                
            except Exception as e2:
                print(f"✗ Fallback failed: {e2}")
                return False
    
    def _update(self):
        """Internal method to continuously read frames"""
        while not self.stopped:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                
                if ret:
                    self.frame = frame
                    self.frame_count += 1
                else:
                    print("⚠ Failed to read frame, reconnecting...")
                    time.sleep(1)
                    self._reconnect()
            else:
                time.sleep(0.1)
    
    def _reconnect(self):
        """Attempt to reconnect to stream"""
        try:
            if self.cap is not None:
                self.cap.release()
            
            # Try streamlink
            streams = streamlink.streams(self.stream_url)
            if streams:
                stream_url = streams['best'].url
                self.cap = cv2.VideoCapture(stream_url)
            else:
                self.cap = cv2.VideoCapture(self.stream_url)
            
            if self.cap.isOpened():
                print("✓ Reconnected to stream")
            
        except Exception as e:
            print(f"✗ Reconnection failed: {e}")
    
    def read(self):
        """Read current frame"""
        return self.frame
    
    def stop(self):
        """Stop video stream"""
        self.stopped = True
        
        if self.cap is not None:
            self.cap.release()
        
        print("Stream stopped")
    
    def is_opened(self):
        """Check if stream is opened"""
        return self.cap is not None and self.cap.isOpened()
    
    def get_frame_count(self):
        """Get total frames read"""
        return self.frame_count
    
    