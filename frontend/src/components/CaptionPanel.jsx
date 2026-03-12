import { useState, useEffect } from 'react';
import ProgressBar from './ProgressBar';
import { generateCaptions, getCaptions, burnCaptions, getSrt, getAss, pollTask, getAvailableTools } from '../api/client';

const CAPTION_STYLES = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'Clean white text with black outline',
    preview: { text: '#FFFFFF', outline: '#000000', bg: null, uppercase: false },
  },
  {
    id: 'box',
    name: 'Box',
    description: 'White text on dark semi-transparent box',
    preview: { text: '#FFFFFF', outline: null, bg: 'rgba(0,0,0,0.7)', uppercase: false },
  },
  {
    id: 'bold_pop',
    name: 'Bold Pop',
    description: 'Large bold uppercase with thick outline',
    preview: { text: '#FFFFFF', outline: '#000000', bg: null, uppercase: true },
  },
  {
    id: 'highlight',
    name: 'Highlight',
    description: 'Word-by-word highlight (Hormozi style)',
    preview: { text: '#666666', outline: '#000000', bg: null, uppercase: true, highlight: '#FFFFFF' },
  },
  {
    id: 'brand_light',
    name: 'Brand Light',
    description: 'Dark text on beige background',
    preview: { text: '#141e27', outline: null, bg: '#e0ddaa', uppercase: false },
  },
  {
    id: 'brand_dark',
    name: 'Brand Dark',
    description: 'Beige text on dark background',
    preview: { text: '#e0ddaa', outline: null, bg: '#141e27', uppercase: false },
  },
];

function StylePreview({ style, selected, onSelect }) {
  const p = style.preview;
  const sampleWords = p.uppercase ? 'THIS IS HOW' : 'This is how';

  return (
    <button
      onClick={() => onSelect(style.id)}
      className={`text-left p-3 rounded-lg border-2 transition-all ${
        selected
          ? 'border-[#e0ddaa] bg-[#1a1f2e]'
          : 'border-gray-700/50 bg-[#0f1419] hover:border-gray-600'
      }`}
    >
      {/* Mini preview */}
      <div className="bg-gray-900 rounded h-14 flex items-end justify-center pb-2 mb-2 relative overflow-hidden">
        {/* Fake video frame lines */}
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-3 left-3 right-6 h-1 bg-gray-600 rounded" />
          <div className="absolute top-6 left-3 right-10 h-1 bg-gray-600 rounded" />
        </div>

        <span
          className="text-xs font-bold relative z-10 px-1.5 py-0.5 rounded"
          style={{
            color: p.text,
            backgroundColor: p.bg || 'transparent',
            textShadow: p.outline
              ? `1px 1px 0 ${p.outline}, -1px -1px 0 ${p.outline}, 1px -1px 0 ${p.outline}, -1px 1px 0 ${p.outline}`
              : 'none',
          }}
        >
          {p.highlight ? (
            <>
              <span style={{ color: p.text }}>THIS </span>
              <span style={{ color: p.highlight }}>IS </span>
              <span style={{ color: p.text }}>HOW</span>
            </>
          ) : (
            sampleWords
          )}
        </span>
      </div>

      <p className="text-sm font-medium text-gray-200">{style.name}</p>
      <p className="text-xs text-gray-500 mt-0.5">{style.description}</p>
    </button>
  );
}

export default function CaptionPanel({ projectName, stages, onComplete }) {
  const [captions, setCaptions] = useState([]);
  const [style, setStyle] = useState('classic');
  const [renderer, setRenderer] = useState('auto');
  const [tools, setTools] = useState({});
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressStatus, setProgressStatus] = useState('');
  const [substeps, setSubsteps] = useState([]);
  const [error, setError] = useState('');
  const [srtContent, setSrtContent] = useState('');
  const [assContent, setAssContent] = useState('');

  const loadCaptions = async () => {
    try {
      const data = await getCaptions(projectName);
      setCaptions(data);
    } catch (e) {
      // No captions yet
    }
  };

  useEffect(() => {
    if (stages.captions === 'complete') loadCaptions();
  }, [stages.captions]);

  useEffect(() => {
    getAvailableTools().then(setTools).catch(() => {});
  }, []);

  const handleGenerate = async () => {
    setProcessing(true);
    setError('');
    setProgress(10);
    const styleName = CAPTION_STYLES.find(s => s.id === style)?.name || style;
    setProgressStatus(`Generating captions (${styleName})...`);
    setSubsteps([
      { label: 'Generate captions + SRT + ASS', status: 'active' },
    ]);
    try {
      const result = await generateCaptions(projectName, style);
      setProgress(100);
      setProgressStatus(`Generated ${result.caption_count} captions — ${result.style_name}`);
      setSubsteps([{ label: 'Generate captions + SRT + ASS', status: 'complete' }]);
      await loadCaptions();
      onComplete();
    } catch (e) {
      setError(e.message);
      setProgressStatus('Failed');
    } finally {
      setProcessing(false);
    }
  };

  const handleBurn = async () => {
    setProcessing(true);
    setError('');
    setProgress(5);
    setProgressStatus('Starting caption burn...');
    setSubsteps([
      { label: 'Render captioned video', status: 'active' },
    ]);

    try {
      const task = await burnCaptions(projectName, style, renderer);

      await pollTask(task.task_id, (t) => {
        setProgress(t.progress);
        if (t.message) setProgressStatus(t.message);
      }, 2000);

      setProgress(100);
      setProgressStatus('Captions burned into video');
      setSubsteps([{ label: 'Render captioned video', status: 'complete' }]);
      onComplete();
    } catch (e) {
      setError(e.message);
      setProgressStatus('Failed');
    } finally {
      setProcessing(false);
    }
  };

  const handlePreviewSrt = async () => {
    try {
      const data = await getSrt(projectName);
      setSrtContent(data.content);
      setAssContent('');
    } catch (e) {
      setError(e.message);
    }
  };

  const handlePreviewAss = async () => {
    try {
      const data = await getAss(projectName);
      setAssContent(data.content);
      setSrtContent('');
    } catch (e) {
      setError(e.message);
    }
  };

  const hasTranscript = ['correction', 'cleanup', 'editing', 'transcription'].some(
    s => stages[s] === 'complete'
  );

  if (!hasTranscript) {
    return <p className="text-gray-500 text-sm">Complete transcription first.</p>;
  }

  return (
    <div className="space-y-4">
      {/* Style selection */}
      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-2">Caption Style</h3>
        <div className="grid grid-cols-3 gap-2">
          {CAPTION_STYLES.map((s) => (
            <StylePreview
              key={s.id}
              style={s}
              selected={style === s.id}
              onSelect={setStyle}
            />
          ))}
        </div>
      </div>

      {/* Renderer selection */}
      {(tools.moviepy || tools.pycaps) && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">Renderer:</span>
          <select
            value={renderer}
            onChange={(e) => setRenderer(e.target.value)}
            className="bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-sm text-white"
          >
            <option value="auto">Auto{tools.moviepy ? ' (MoviePy)' : ' (Pillow)'}</option>
            <option value="pillow">Pillow (default)</option>
            {tools.moviepy && <option value="moviepy">MoviePy (single-pass)</option>}
          </select>
        </div>
      )}

      {/* Actions */}
      {!processing && (
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            className="bg-[#e0ddaa] text-[#141e27] px-4 py-2 rounded text-sm font-medium hover:bg-[#d4d19e]"
          >
            Generate Captions
          </button>
          {stages.captions === 'complete' && (
            <button
              onClick={handleBurn}
              className="bg-gray-700 text-gray-200 px-4 py-2 rounded text-sm hover:bg-gray-600"
            >
              Burn into Video
            </button>
          )}
        </div>
      )}

      {/* Progress */}
      {(processing || progress === 100) && (
        <ProgressBar progress={progress} status={progressStatus} substeps={substeps} />
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded p-3 text-sm text-red-300">{error}</div>
      )}

      {/* Preview buttons */}
      {stages.captions === 'complete' && !processing && (
        <div className="flex gap-2">
          <button onClick={handlePreviewSrt} className="text-xs text-[#e0ddaa] hover:underline">Preview SRT</button>
          <button onClick={handlePreviewAss} className="text-xs text-[#e0ddaa] hover:underline">Preview ASS</button>
        </div>
      )}

      {/* Caption preview */}
      {captions.length > 0 && !srtContent && !assContent && !processing && (
        <div className="space-y-1 max-h-96 overflow-y-auto">
          <h4 className="text-xs text-gray-500 mb-2">{captions.length} captions</h4>
          {captions.map((cap) => (
            <div key={cap.id} className="flex gap-2 text-xs py-1 border-b border-gray-800">
              <span className="text-gray-500 font-mono w-20 shrink-0">
                {Math.floor(cap.start / 60)}:{Math.floor(cap.start % 60).toString().padStart(2, '0')}
              </span>
              <span className="text-gray-300">{cap.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* SRT/ASS preview */}
      {(srtContent || assContent) && (
        <div className="bg-[#0f1419] border border-gray-700 rounded p-3 max-h-96 overflow-y-auto">
          <div className="flex justify-between mb-2">
            <span className="text-xs text-gray-500">{srtContent ? 'SRT' : 'ASS'} Preview</span>
            <button onClick={() => { setSrtContent(''); setAssContent(''); }} className="text-xs text-gray-500 hover:text-gray-300">Close</button>
          </div>
          <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">{srtContent || assContent}</pre>
        </div>
      )}
    </div>
  );
}
