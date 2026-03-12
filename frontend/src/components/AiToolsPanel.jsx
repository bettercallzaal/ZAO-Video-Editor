import { useState, useEffect } from 'react';
import ProgressBar from './ProgressBar';
import {
  getAvailableTools, pollTask,
  upscaleVideo, removeBackground, detectScenes, enhanceAudio,
  generateThumbnails, listThumbnails, getThumbnailUrl,
  generateVideo, generateBroll, textToSpeech,
  generateMusic, mixMusic, generateAiThumbnail,
} from '../api/client';

function ToolCard({ name, description, available, children }) {
  return (
    <div className={`border rounded-lg p-3 ${available ? 'border-gray-700 bg-[#0f1419]' : 'border-gray-800/50 bg-[#0a0e12] opacity-60'}`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-200">{name}</h4>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${available ? 'bg-green-900/50 text-green-400' : 'bg-gray-800 text-gray-500'}`}>
          {available ? 'ready' : 'not installed'}
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-2">{description}</p>
      {available && children}
    </div>
  );
}

export default function AiToolsPanel({ projectName, stages, onComplete, onSeek }) {
  const [tools, setTools] = useState({});
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressStatus, setProgressStatus] = useState('');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Tool-specific state
  const [upscaleScale, setUpscaleScale] = useState(2);
  const [bgColor, setBgColor] = useState('#00FF00');
  const [sceneThreshold, setSceneThreshold] = useState(27);
  const [scenes, setScenes] = useState(null);
  const [thumbnails, setThumbnails] = useState([]);
  const [videoPrompt, setVideoPrompt] = useState('');
  const [videoDuration, setVideoDuration] = useState(6);
  const [ttsText, setTtsText] = useState('');
  const [ttsLang, setTtsLang] = useState('en');
  const [musicPrompt, setMusicPrompt] = useState('');
  const [musicDuration, setMusicDuration] = useState(30);
  const [musicVolume, setMusicVolume] = useState(0.15);
  const [thumbPrompt, setThumbPrompt] = useState('');

  useEffect(() => {
    getAvailableTools().then(setTools).catch(() => {});
  }, []);

  const hasVideo = stages.upload === 'complete' || stages.assembly === 'complete';
  const hasGPU = tools.torch_gpu;

  const runTask = async (label, apiCall) => {
    setProcessing(true);
    setError('');
    setResult(null);
    setProgress(5);
    setProgressStatus(`${label}...`);
    try {
      const task = await apiCall();
      if (task.task_id) {
        // Background task — poll
        const final = await pollTask(task.task_id, (t) => {
          setProgress(t.progress);
          if (t.message) setProgressStatus(t.message);
        }, 2000);
        setProgress(100);
        setProgressStatus(`${label} complete`);
        setResult(final.result);
        if (onComplete) onComplete();
      } else {
        // Synchronous result
        setProgress(100);
        setProgressStatus(`${label} complete`);
        setResult(task);
        if (onComplete) onComplete();
      }
    } catch (e) {
      setError(e.message);
      setProgressStatus('Failed');
    } finally {
      setProcessing(false);
    }
  };

  const loadThumbnails = async () => {
    try {
      const data = await listThumbnails(projectName);
      setThumbnails(data);
    } catch (e) {}
  };

  return (
    <div className="space-y-4 overflow-y-auto">
      {/* Status bar */}
      {(processing || progress > 0) && (
        <ProgressBar progress={progress} status={progressStatus} />
      )}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded p-2 text-xs text-red-300">{error}</div>
      )}

      {/* === TIER 1: CPU TOOLS === */}
      <div>
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
          Enhancement Tools {!hasVideo && '— upload a video first'}
        </h3>

        <div className="grid grid-cols-1 gap-3">
          {/* Audio Enhancement */}
          <ToolCard
            name="Audio Enhancement"
            description="Remove noise, normalize levels. Uses Meta Denoiser or ffmpeg filters."
            available={hasVideo}
          >
            <button
              onClick={() => runTask('Enhancing audio', () => enhanceAudio(projectName))}
              disabled={processing}
              className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
            >
              Enhance Audio
            </button>
            {tools.denoiser && <span className="text-[10px] text-green-500 ml-2">Meta Denoiser</span>}
            {!tools.denoiser && <span className="text-[10px] text-gray-500 ml-2">ffmpeg fallback</span>}
          </ToolCard>

          {/* Scene Detection */}
          <ToolCard
            name="Scene Detection"
            description="Detect shot boundaries and auto-generate YouTube chapters."
            available={hasVideo && tools.scenedetect}
          >
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-gray-500">Sensitivity:</label>
              <input
                type="range" min="10" max="50" step="1" value={sceneThreshold}
                onChange={(e) => setSceneThreshold(Number(e.target.value))}
                className="w-20 h-1 accent-[#e0ddaa]"
              />
              <span className="text-[10px] text-gray-400 font-mono w-6">{sceneThreshold}</span>
              <button
                onClick={async () => {
                  setProcessing(true); setError('');
                  try {
                    const data = await detectScenes(projectName, sceneThreshold);
                    setScenes(data);
                    setProgress(100);
                    setProgressStatus(`Found ${data.scene_count} scenes`);
                  } catch (e) { setError(e.message); }
                  finally { setProcessing(false); }
                }}
                disabled={processing}
                className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
              >
                Detect Scenes
              </button>
            </div>
            {scenes && (
              <div className="mt-2 space-y-1">
                <p className="text-xs text-gray-400">{scenes.scene_count} scenes detected</p>
                <pre className="text-[10px] text-gray-500 font-mono bg-[#1a1f2e] rounded p-2 max-h-32 overflow-y-auto">
                  {scenes.chapters}
                </pre>
                {scenes.scenes.map((s) => (
                  <button key={s.id} onClick={() => onSeek(s.start)}
                    className="text-[10px] text-[#e0ddaa] hover:underline mr-2">
                    Scene {s.id + 1} ({Math.floor(s.start / 60)}:{Math.floor(s.start % 60).toString().padStart(2, '0')})
                  </button>
                ))}
              </div>
            )}
          </ToolCard>

          {/* Upscale */}
          <ToolCard
            name="Video Upscale"
            description="Upscale resolution 2x or 4x. Uses Real-ESRGAN (AI) or ffmpeg lanczos."
            available={hasVideo}
          >
            <div className="flex items-center gap-2">
              <select
                value={upscaleScale}
                onChange={(e) => setUpscaleScale(Number(e.target.value))}
                className="bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-xs text-white"
              >
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
              <button
                onClick={() => runTask(`Upscaling ${upscaleScale}x`, () => upscaleVideo(projectName, upscaleScale))}
                disabled={processing}
                className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
              >
                Upscale
              </button>
              {tools.realesrgan && <span className="text-[10px] text-green-500">Real-ESRGAN</span>}
              {!tools.realesrgan && <span className="text-[10px] text-gray-500">lanczos fallback</span>}
            </div>
          </ToolCard>

          {/* Background Removal */}
          <ToolCard
            name="Background Removal"
            description="Remove video background. Replace with solid color for green-screen."
            available={hasVideo && tools.rembg}
          >
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-gray-500">BG:</label>
              <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)}
                className="w-6 h-6 rounded border-0 cursor-pointer" />
              <button
                onClick={() => runTask('Removing background', () => removeBackground(projectName, bgColor))}
                disabled={processing}
                className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
              >
                Remove Background
              </button>
            </div>
          </ToolCard>

          {/* Thumbnails */}
          <ToolCard
            name="Thumbnails"
            description="Extract candidate thumbnail frames from your video."
            available={hasVideo}
          >
            <div className="flex items-center gap-2">
              <button
                onClick={async () => {
                  setProcessing(true); setError('');
                  try {
                    await generateThumbnails(projectName, 5);
                    await loadThumbnails();
                    setProgress(100);
                    setProgressStatus('Thumbnails extracted');
                  } catch (e) { setError(e.message); }
                  finally { setProcessing(false); }
                }}
                disabled={processing}
                className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
              >
                Extract Thumbnails
              </button>
            </div>
            {thumbnails.length > 0 && (
              <div className="flex gap-2 mt-2 overflow-x-auto">
                {thumbnails.map((t, i) => (
                  <img
                    key={i}
                    src={getThumbnailUrl(projectName, t.filename)}
                    alt={`Thumb ${i + 1}`}
                    className="h-16 rounded border border-gray-700 cursor-pointer hover:border-[#e0ddaa]"
                  />
                ))}
              </div>
            )}
          </ToolCard>
        </div>
      </div>

      {/* === TIER 2: GPU TOOLS === */}
      <div>
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
          AI Generation {!hasGPU && '— requires NVIDIA GPU'}
        </h3>

        <div className="grid grid-cols-1 gap-3">
          {/* Video Generation */}
          <ToolCard
            name="B-Roll Generation (LTX-2)"
            description="Generate video clips from text prompts. 6-20 seconds, up to 4K."
            available={tools.ltx_video}
          >
            <div className="space-y-2">
              <textarea
                value={videoPrompt}
                onChange={(e) => setVideoPrompt(e.target.value)}
                placeholder="Describe the B-roll you want... e.g., 'aerial view of a city skyline at sunset, cinematic'"
                className="w-full bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1.5 text-xs text-white resize-none"
                rows={2}
              />
              <div className="flex items-center gap-2">
                <select value={videoDuration} onChange={(e) => setVideoDuration(Number(e.target.value))}
                  className="bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-xs text-white">
                  {[6, 8, 10, 12, 14, 16, 18, 20].map(d => (
                    <option key={d} value={d}>{d}s</option>
                  ))}
                </select>
                <button
                  onClick={() => runTask('Generating video', () => generateVideo(projectName, videoPrompt, videoDuration))}
                  disabled={processing || !videoPrompt.trim()}
                  className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
                >
                  Generate
                </button>
                <button
                  onClick={() => runTask('Generating B-roll', () => generateBroll(projectName, videoPrompt, videoDuration, 3))}
                  disabled={processing || !videoPrompt.trim()}
                  className="text-xs bg-gray-700 text-gray-200 px-3 py-1.5 rounded hover:bg-gray-600 disabled:opacity-50"
                >
                  Generate 3 Clips
                </button>
              </div>
            </div>
          </ToolCard>

          {/* Text-to-Speech */}
          <ToolCard
            name="Voiceover (Coqui XTTS-v2)"
            description="Generate speech from text. Clone any voice from a 6-second sample."
            available={tools.coqui_tts}
          >
            <div className="space-y-2">
              <textarea
                value={ttsText}
                onChange={(e) => setTtsText(e.target.value)}
                placeholder="Enter the text you want spoken..."
                className="w-full bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1.5 text-xs text-white resize-none"
                rows={3}
              />
              <div className="flex items-center gap-2">
                <select value={ttsLang} onChange={(e) => setTtsLang(e.target.value)}
                  className="bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-xs text-white">
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                  <option value="pt">Portuguese</option>
                  <option value="it">Italian</option>
                  <option value="ja">Japanese</option>
                  <option value="ko">Korean</option>
                  <option value="zh-cn">Chinese</option>
                </select>
                <button
                  onClick={() => runTask('Generating voiceover', () => textToSpeech(projectName, ttsText, ttsLang))}
                  disabled={processing || !ttsText.trim()}
                  className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
                >
                  Generate Voiceover
                </button>
              </div>
            </div>
          </ToolCard>

          {/* Music Generation */}
          <ToolCard
            name="Background Music (MusicGen)"
            description="Generate royalty-free music from text descriptions."
            available={tools.musicgen}
          >
            <div className="space-y-2">
              <textarea
                value={musicPrompt}
                onChange={(e) => setMusicPrompt(e.target.value)}
                placeholder="Describe the music... e.g., 'upbeat corporate background, soft piano'"
                className="w-full bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1.5 text-xs text-white resize-none"
                rows={2}
              />
              <div className="flex items-center gap-2">
                <select value={musicDuration} onChange={(e) => setMusicDuration(Number(e.target.value))}
                  className="bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-xs text-white">
                  <option value={15}>15s</option>
                  <option value={30}>30s</option>
                  <option value={60}>60s</option>
                </select>
                <button
                  onClick={() => runTask('Generating music', () => generateMusic(projectName, musicPrompt, musicDuration))}
                  disabled={processing || !musicPrompt.trim()}
                  className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
                >
                  Generate
                </button>
                <button
                  onClick={() => runTask('Mixing music', () => mixMusic(projectName, musicVolume))}
                  disabled={processing}
                  className="text-xs bg-gray-700 text-gray-200 px-3 py-1.5 rounded hover:bg-gray-600 disabled:opacity-50"
                >
                  Mix into Video
                </button>
                <label className="text-[10px] text-gray-500">Vol:</label>
                <input
                  type="range" min="0.05" max="0.5" step="0.05" value={musicVolume}
                  onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
                  className="w-14 h-1 accent-[#e0ddaa]"
                />
              </div>
            </div>
          </ToolCard>

          {/* AI Thumbnail */}
          <ToolCard
            name="AI Thumbnail (Stable Diffusion)"
            description="Generate custom thumbnails from text prompts."
            available={tools.diffusers && tools.torch_gpu}
          >
            <div className="flex items-center gap-2">
              <input
                value={thumbPrompt}
                onChange={(e) => setThumbPrompt(e.target.value)}
                placeholder="Thumbnail description..."
                className="flex-1 bg-[#1a1f2e] border border-gray-700 rounded px-2 py-1 text-xs text-white"
              />
              <button
                onClick={() => runTask('Generating thumbnail', () => generateAiThumbnail(projectName, thumbPrompt))}
                disabled={processing || !thumbPrompt.trim()}
                className="text-xs bg-[#e0ddaa] text-[#141e27] px-3 py-1.5 rounded font-medium hover:bg-[#d4d19e] disabled:opacity-50"
              >
                Generate
              </button>
            </div>
          </ToolCard>
        </div>
      </div>

      {/* Install guide for missing tools */}
      <div className="border border-gray-800 rounded-lg p-3">
        <h4 className="text-xs font-medium text-gray-400 mb-2">Install Optional Tools</h4>
        <div className="space-y-1 text-[10px] font-mono text-gray-500">
          {!tools.scenedetect && <p>pip install scenedetect[opencv]  <span className="text-gray-600"># scene detection</span></p>}
          {!tools.rembg && <p>pip install rembg  <span className="text-gray-600"># background removal</span></p>}
          {!tools.denoiser && <p>pip install denoiser  <span className="text-gray-600"># Meta audio denoiser</span></p>}
          {!tools.realesrgan && <p># Install realesrgan-ncnn-vulkan from GitHub releases  <span className="text-gray-600"># AI upscaling</span></p>}
          {!tools.ltx_video && <p>pip install diffusers transformers accelerate  <span className="text-gray-600"># LTX-2 video gen</span></p>}
          {!tools.coqui_tts && <p>pip install TTS  <span className="text-gray-600"># voice cloning</span></p>}
          {!tools.musicgen && <p>pip install audiocraft  <span className="text-gray-600"># music generation</span></p>}
        </div>
      </div>
    </div>
  );
}
