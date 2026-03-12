import { useRef, useState, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react';

const VideoPlayer = forwardRef(({ src, seekTime, children, onTimeUpdate }, ref) => {
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useImperativeHandle(ref, () => ({
    getCurrentTime: () => videoRef.current?.currentTime || 0,
    getDuration: () => videoRef.current?.duration || 0,
    seek: (time) => {
      if (videoRef.current) videoRef.current.currentTime = time;
    },
    getContainerRect: () => containerRef.current?.getBoundingClientRect(),
    getVideoRect: () => {
      const video = videoRef.current;
      if (!video) return null;
      const container = containerRef.current;
      if (!container) return null;
      // Calculate actual video display area within the container
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      const vw = video.videoWidth || 1920;
      const vh = video.videoHeight || 1080;
      const scale = Math.min(cw / vw, ch / vh);
      const displayW = vw * scale;
      const displayH = vh * scale;
      const offsetX = (cw - displayW) / 2;
      const offsetY = (ch - displayH) / 2;
      return { x: offsetX, y: offsetY, width: displayW, height: displayH, videoWidth: vw, videoHeight: vh };
    },
  }));

  useEffect(() => {
    if (seekTime !== null && seekTime !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTime;
    }
  }, [seekTime]);

  const handleTimeUpdate = useCallback(() => {
    const t = videoRef.current?.currentTime || 0;
    setCurrentTime(t);
    if (onTimeUpdate) onTimeUpdate(t);
  }, [onTimeUpdate]);

  const handleLoadedMetadata = () => {
    setDuration(videoRef.current?.duration || 0);
  };

  if (!src) {
    return (
      <div className="flex-1 flex items-center justify-center bg-black/50 text-gray-500">
        <p>Upload a video to get started</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 flex items-center justify-center bg-black relative">
      <video
        ref={videoRef}
        src={src}
        controls
        className="w-full h-full object-contain"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
      />
      {/* Overlay layer for captions, positioned over video */}
      {children}
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
export default VideoPlayer;
