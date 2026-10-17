import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import ForceGraph2D, { ForceGraphMethods } from 'react-force-graph-2d';
import { HighlightGraph, HighlightNode, HighlightEdge } from '@/api/types';
import { SEMANTIC_COLORS, SemanticRole } from '@/design/tokens';
import { formatRupees, formatElapsedOffset } from '@/lib/formatters';
import {
  Play,
  Pause,
  RotateCcw,
  SkipForward,
  Maximize2,
  Layers,
  Info,
  CheckCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';

interface GraphCanvasProps {
  data: HighlightGraph | null;
  onNodeClick?: (nodeId: string) => void;
  hoveredAccountId?: string | null;
  onHoverNode?: (nodeId: string | null) => void;
  timelineStep?: number;
  theftTimestamp?: number;
  className?: string;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  onNodeClick,
  hoveredAccountId,
  onHoverNode,
  theftTimestamp = 1792038000,
  className,
}) => {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Playback & Scrubber State
  const [currentSequence, setCurrentSequence] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [showLegend, setShowLegend] = useState<boolean>(true);
  const [focusMode, setFocusMode] = useState<boolean>(false);

  // Layer Toggles
  const [layers, setLayers] = useState({
    moneyFlow: true,
    sharedDevices: true,
    clearedAccounts: true,
    linkedRings: true,
  });

  // Track max sequence from timed edges
  const maxSequence = useMemo(() => {
    if (!data?.edges) return 0;
    let maxSeq = 0;
    for (const e of data.edges) {
      if (e.sequence_index && e.sequence_index > maxSeq) {
        maxSeq = e.sequence_index;
      }
    }
    // If no sequence_index, infer from number of hops
    return Math.max(maxSeq, 5);
  }, [data]);

  // Handle window resizing
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Set sequence to max when new case loads
  useEffect(() => {
    if (data && maxSequence > 0) {
      setCurrentSequence(maxSequence);
    }
  }, [data, maxSequence]);

  // Playback Timer
  useEffect(() => {
    if (!isPlaying) return;
    const intervalTime = 1200 / playbackSpeed;
    const timer = setInterval(() => {
      setCurrentSequence((prev) => {
        if (prev >= maxSequence) {
          setIsPlaying(false);
          return maxSequence;
        }
        return prev + 1;
      });
    }, intervalTime);

    return () => clearInterval(timer);
  }, [isPlaying, maxSequence, playbackSpeed]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        setCurrentSequence((s) => Math.min(s + 1, maxSequence));
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        setCurrentSequence((s) => Math.max(s - 1, 0));
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        setCurrentSequence(0);
        setIsPlaying(true);
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        setFocusMode((f) => !f);
      }
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [maxSequence]);

  // Filtered nodes and edges according to active layers and sequence scrubber
  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };

    const activeNodes = (data.nodes || []).filter((n) => {
      if (!layers.clearedAccounts && n.role === 'cleared') return false;
      if (!layers.linkedRings && n.role === 'linked_ring') return false;
      if (!layers.sharedDevices && n.role === 'shared_device') return false;
      return true;
    });

    const activeNodeIds = new Set(activeNodes.map((n) => n.id));

    const activeLinks = (data.edges || []).filter((e) => {
      const srcId = typeof e.source === 'object' ? (e.source as any).id : e.source;
      const tgtId = typeof e.target === 'object' ? (e.target as any).id : e.target;
      if (!activeNodeIds.has(srcId) || !activeNodeIds.has(tgtId)) return false;

      if (!layers.sharedDevices && e.role === 'shared_device') return false;
      if (!layers.moneyFlow && (e.role === 'mule_recommended' || e.role === 'cash_out')) return false;

      // Filter by scrubber sequence
      if (e.sequence_index && e.sequence_index > currentSequence) {
        return false;
      }
      return true;
    });

    return {
      nodes: activeNodes.map((n) => ({ ...n })),
      links: activeLinks.map((l) => ({ ...l })),
    };
  }, [data, layers, currentSequence]);

  // Center & Fit View
  const handleFitView = useCallback(() => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 40);
    }
  }, []);

  useEffect(() => {
    // Zoom to fit on initial load
    const t = setTimeout(() => {
      handleFitView();
    }, 600);
    return () => clearTimeout(t);
  }, [handleFitView, data]);

  // Custom Node Canvas Renderer
  const drawNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHovered = hoveredAccountId === node.id;
      const isVictim = node.role === 'victim';
      const isFreeze = node.role === 'mule_recommended';
      const isCleared = node.role === 'cleared';
      const isCashout = node.role === 'cash_out';
      const isDevice = node.role === 'shared_device';
      const isLinkedRing = node.role === 'linked_ring';

      const sc = SEMANTIC_COLORS[node.role as SemanticRole] || SEMANTIC_COLORS.neutral;

      // Base radius by role
      let baseRadius = 7;
      if (isVictim) baseRadius = 11;
      else if (isFreeze) baseRadius = 9.5;
      else if (isCashout) baseRadius = 8.5;
      else if (isCleared) baseRadius = 8;
      else if (isDevice) baseRadius = 6.5;

      const r = baseRadius;

      // Dimming in focus mode if not hovered or not related
      const isDimmed = focusMode && hoveredAccountId && !isHovered;
      ctx.globalAlpha = isDimmed ? 0.25 : 1.0;

      // Glow effect for key nodes or hovered
      if (isHovered || isFreeze || isVictim) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI, false);
        ctx.fillStyle = sc.bg;
        ctx.shadowColor = sc.color;
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.restore();
      }

      // Draw Main Node Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = sc.color;
      ctx.fill();

      // Border ring
      ctx.lineWidth = isHovered ? 2.5 : 1.5;
      ctx.strokeStyle = isCleared ? '#34d399' : '#ffffff';
      ctx.stroke();

      // Cleared Decoy Checkmark Badge Ring
      if (isCleared) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 3, 0, 2 * Math.PI, false);
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.6)';
        ctx.stroke();
      }

      // Labels below node
      if (globalScale > 0.8 || isHovered || isVictim || isFreeze) {
        const fontSize = Math.max(3.2, 11 / globalScale);
        ctx.font = `500 ${fontSize}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Label text
        const labelText = node.label || node.id;
        ctx.fillStyle = isHovered ? '#ffffff' : '#cbd5e1';
        ctx.fillText(labelText, node.x, node.y + r + 3);
      }

      ctx.globalAlpha = 1.0;
    },
    [hoveredAccountId, focusMode]
  );

  // Custom Link Canvas Renderer
  const drawLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isDeviceLink = link.role === 'shared_device';
      const isCashout = link.role === 'cash_out';

      ctx.save();

      if (isDeviceLink) {
        // Dashed cyan line for shared hardware
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 1.2;
      } else if (isCashout) {
        ctx.setLineDash([]);
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2.2;
      } else {
        // Money flow link
        ctx.setLineDash([]);
        ctx.strokeStyle = '#f43f5e';
        ctx.lineWidth = 2.0;
      }

      ctx.beginPath();
      ctx.moveTo(link.source.x, link.source.y);
      ctx.lineTo(link.target.x, link.target.y);
      ctx.stroke();

      // Edge Amount Label (if present)
      if (link.amount && globalScale > 0.9) {
        const midX = (link.source.x + link.target.x) / 2;
        const midY = (link.source.y + link.target.y) / 2;
        const amtText = formatRupees(link.amount);

        ctx.font = `600 ${Math.max(3, 9 / globalScale)}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Background pill behind text
        const textWidth = ctx.measureText(amtText).width;
        ctx.fillStyle = 'rgba(14, 21, 38, 0.85)';
        ctx.fillRect(midX - textWidth / 2 - 2, midY - 6, textWidth + 4, 12);

        ctx.fillStyle = isCashout ? '#fbbf24' : '#fb7185';
        ctx.fillText(amtText, midX, midY);
      }

      ctx.restore();
    },
    []
  );

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full bg-[#090d16] dot-grid overflow-hidden flex flex-col ${className || ''}`}
    >
      {/* Canvas Layer */}
      <div className="flex-1 w-full h-full relative">
        <ForceGraph2D
          ref={fgRef as any}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel={(n: any) => `${n.label || n.id}`}
          nodeCanvasObject={drawNode}
          nodePointerAreaPaint={(node: any, color, ctx) => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, 14, 0, 2 * Math.PI, false);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          linkCanvasObject={drawLink}
          linkDirectionalParticles={currentSequence > 0 ? 3 : 0}
          linkDirectionalParticleSpeed={0.007 * playbackSpeed}
          linkDirectionalParticleWidth={2.4}
          linkDirectionalParticleColor={(l: any) =>
            l.role === 'shared_device' ? '#22d3ee' : '#fda4af'
          }
          onNodeClick={(n: any) => onNodeClick?.(n.id)}
          onNodeHover={(n: any) => onHoverNode?.(n ? n.id : null)}
          cooldownTicks={120}
          d3AlphaDecay={0.03}
          d3VelocityDecay={0.2}
        />
      </div>

      {/* Floating Control Cluster (Top Left) */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleFitView}
          leftIcon={<Maximize2 className="w-3.5 h-3.5" />}
          className="bg-[#0e1526]/85 backdrop-blur-md shadow-lg"
        >
          Fit View
        </Button>

        {/* Layer Toggle Dropdown */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-[#0e1526]/85 border border-white/10 backdrop-blur-md shadow-lg text-xs">
          <button
            onClick={() => setLayers((l) => ({ ...l, moneyFlow: !l.moneyFlow }))}
            className={`px-2 py-1 rounded-lg transition-colors cursor-pointer ${
              layers.moneyFlow ? 'bg-rose-500/20 text-rose-300 font-semibold' : 'text-slate-400'
            }`}
          >
            Money Trail
          </button>
          <button
            onClick={() => setLayers((l) => ({ ...l, sharedDevices: !l.sharedDevices }))}
            className={`px-2 py-1 rounded-lg transition-colors cursor-pointer ${
              layers.sharedDevices ? 'bg-cyan-500/20 text-cyan-300 font-semibold' : 'text-slate-400'
            }`}
          >
            Hardware
          </button>
          <button
            onClick={() => setLayers((l) => ({ ...l, clearedAccounts: !l.clearedAccounts }))}
            className={`px-2 py-1 rounded-lg transition-colors cursor-pointer ${
              layers.clearedAccounts ? 'bg-emerald-500/20 text-emerald-300 font-semibold' : 'text-slate-400'
            }`}
          >
            Decoys
          </button>
        </div>
      </div>

      {/* Floating Scrubber Bar (Bottom Center) */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 w-[92%] max-w-xl">
        <div className="p-3 rounded-2xl border border-white/12 bg-[#0e1526]/90 backdrop-blur-md shadow-2xl flex flex-col gap-2.5">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-200">Forensic Money Trail</span>
              <span className="text-slate-400 font-mono">
                Hop {currentSequence} of {maxSequence}
              </span>
            </div>

            {/* Elapsed Time Ticker since theft */}
            <div className="flex items-center gap-1.5 font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>{formatElapsedOffset(theftTimestamp, theftTimestamp + currentSequence * 180)}</span>
            </div>
          </div>

          {/* Scrubber Range Slider */}
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={maxSequence}
              value={currentSequence}
              onChange={(e) => {
                setIsPlaying(false);
                setCurrentSequence(Number(e.target.value));
              }}
              className="flex-1 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
          </div>

          {/* Controls: Play, Step, Restart, Speed */}
          <div className="flex items-center justify-between pt-1 border-t border-white/5">
            <div className="flex items-center gap-1.5">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsPlaying(!isPlaying)}
                leftIcon={isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
              >
                {isPlaying ? 'Pause' : 'Play Flow'}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentSequence((s) => Math.min(s + 1, maxSequence))}
                leftIcon={<SkipForward className="w-3.5 h-3.5" />}
                disabled={currentSequence >= maxSequence}
              >
                Step
              </Button>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setCurrentSequence(0);
                  setIsPlaying(true);
                }}
                aria-label="Restart timeline"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 hidden sm:inline">Speed:</span>
              <button
                onClick={() => setPlaybackSpeed(playbackSpeed === 1 ? 2 : 1)}
                className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 font-mono text-xs border border-white/10 cursor-pointer"
              >
                {playbackSpeed}x
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Legend (Bottom Right) */}
      {showLegend && (
        <div className="absolute top-4 right-4 z-10 p-3 rounded-xl border border-white/10 bg-[#0e1526]/85 backdrop-blur-md shadow-xl text-xs space-y-1.5 select-none hidden lg:block">
          <div className="font-semibold text-slate-200 border-b border-white/10 pb-1 mb-1.5 flex items-center justify-between">
            <span>Graph Legend</span>
            <button
              onClick={() => setShowLegend(false)}
              className="text-slate-500 hover:text-slate-300 ml-2"
            >
              ×
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shrink-0" />
            <span className="text-slate-300">Victim Account</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0" />
            <span className="text-slate-300">Mule (Freeze Rec.)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
            <span className="text-slate-300">Cash-out Point</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
            <span className="text-slate-300">Cleared Decoy</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 shrink-0" />
            <span className="text-slate-300">Shared Hardware</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-violet-500 shrink-0" />
            <span className="text-slate-300">Linked Ring</span>
          </div>
        </div>
      )}
    </div>
  );
};
