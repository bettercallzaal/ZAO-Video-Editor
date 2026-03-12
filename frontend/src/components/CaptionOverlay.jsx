import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * Renders live-preview captions directly over the video player.
 * Supports drag-to-reposition. Position is stored as % of video dimensions.
 */

const STYLE_CSS = {
  classic: {
    color: '#FFFFFF',
    textShadow: '2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 0 2px 0 #000, 0 -2px 0 #000, 2px 0 0 #000, -2px 0 0 #000',
    fontWeight: 'bold',
    fontSize: '1.4em',
  },
  box: {
    color: '#FFFFFF',
    backgroundColor: 'rgba(0,0,0,0.7)',
    padding: '4px 12px',
    borderRadius: '6px',
    fontWeight: 'bold',
    fontSize: '1.3em',
  },
  bold_pop: {
    color: '#FFFFFF',
    textShadow: '3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 0 3px 0 #000, 0 -3px 0 #000, 3px 0 0 #000, -3px 0 0 #000',
    fontWeight: '900',
    fontSize: '1.6em',
    textTransform: 'uppercase',
  },
  highlight: {
    textShadow: '3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 0 3px 0 #000, 0 -3px 0 #000, 3px 0 0 #000, -3px 0 0 #000',
    fontWeight: '900',
    fontSize: '1.6em',
    textTransform: 'uppercase',
  },
  brand_light: {
    color: '#141e27',
    backgroundColor: '#e0ddaa',
    padding: '4px 12px',
    borderRadius: '6px',
    fontWeight: 'bold',
    fontSize: '1.2em',
  },
  brand_dark: {
    color: '#e0ddaa',
    backgroundColor: '#141e27',
    padding: '4px 12px',
    borderRadius: '6px',
    fontWeight: 'bold',
    fontSize: '1.2em',
  },
};

export default function CaptionOverlay({
  captions,
  currentTime,
  style = 'classic',
  position,          // { x: 50, y: 88 } — % of video area
  onPositionChange,  // called with { x, y } when user drags
  videoRect,         // from VideoPlayer ref
  selectedId,
  onSelect,
}) {
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef(null);
  const overlayRef = useRef(null);

  // Find the active caption at current time
  const activeCaption = captions.find(
    c => currentTime >= c.start && currentTime <= c.end
  );

  // For highlight style, find which word is active
  let activeWordIdx = -1;
  if (style === 'highlight' && activeCaption?.word_timing) {
    activeWordIdx = activeCaption.word_timing.findIndex(
      wt => currentTime >= wt.start && currentTime <= wt.end
    );
  }

  const pos = position || { x: 50, y: 88 };

  const handleMouseDown = useCallback((e) => {
    if (!videoRect || !onPositionChange) return;
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
    dragStart.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      posX: pos.x,
      posY: pos.y,
    };
  }, [videoRect, onPositionChange, pos]);

  useEffect(() => {
    if (!dragging) return;
    const handleMouseMove = (e) => {
      if (!dragStart.current || !videoRect) return;
      const dx = e.clientX - dragStart.current.mouseX;
      const dy = e.clientY - dragStart.current.mouseY;
      const newX = Math.max(5, Math.min(95, dragStart.current.posX + (dx / videoRect.width) * 100));
      const newY = Math.max(5, Math.min(95, dragStart.current.posY + (dy / videoRect.height) * 100));
      onPositionChange({ x: newX, y: newY });
    };
    const handleMouseUp = () => {
      setDragging(false);
      dragStart.current = null;
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragging, videoRect, onPositionChange]);

  if (!activeCaption || !videoRect) return null;

  const isSelected = selectedId === activeCaption.id;
  const cssStyle = STYLE_CSS[style] || STYLE_CSS.classic;

  // Position within the video display area
  const overlayStyle = {
    position: 'absolute',
    left: videoRect.x + (pos.x / 100) * videoRect.width,
    top: videoRect.y + (pos.y / 100) * videoRect.height,
    transform: 'translate(-50%, -50%)',
    cursor: onPositionChange ? (dragging ? 'grabbing' : 'grab') : 'default',
    userSelect: 'none',
    pointerEvents: 'auto',
    maxWidth: videoRect.width * 0.85,
    textAlign: 'center',
    fontFamily: "'Montserrat', 'Arial Black', 'Helvetica Neue', sans-serif",
    lineHeight: 1.3,
    zIndex: 20,
    ...cssStyle,
  };

  // Outline for selected/draggable state
  if (isSelected || dragging) {
    overlayStyle.outline = '2px dashed rgba(224, 221, 170, 0.7)';
    overlayStyle.outlineOffset = '4px';
  }

  const handleClick = (e) => {
    e.stopPropagation();
    if (onSelect) onSelect(activeCaption.id);
  };

  const renderText = () => {
    const text = activeCaption.text;

    if (style === 'highlight' && activeCaption.word_timing) {
      return activeCaption.word_timing.map((wt, i) => (
        <span
          key={i}
          style={{
            color: i === activeWordIdx ? '#FFFFFF' : '#666666',
            transition: 'color 0.1s',
          }}
        >
          {wt.word}{i < activeCaption.word_timing.length - 1 ? ' ' : ''}
        </span>
      ));
    }

    return text;
  };

  return (
    <div
      ref={overlayRef}
      style={overlayStyle}
      onMouseDown={handleMouseDown}
      onClick={handleClick}
    >
      {renderText()}
    </div>
  );
}
