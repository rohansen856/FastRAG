"use client";

import { useEffect, useRef } from "react";

interface Props {
  /** When true, sphere radius follows the mic analyser like the old waveform. */
  active?: boolean;
  sample?: () => Uint8Array | null;
}

export function AnimatedSphere({ active = false, sample }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef(0);
  const activeRef = useRef(active);
  const sampleRef = useRef(sample);

  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  useEffect(() => {
    sampleRef.current = sample;
  }, [sample]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const chars = "░▒▓█▀▄▌▐│─┤├┴┬╭╮╰╯";
    let time = 0;
    let canvasFont = "12px sans-serif";

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const family = getComputedStyle(document.body).fontFamily || "Outfit, sans-serif";
      canvasFont = `12px ${family}`;
    };

    resize();
    window.addEventListener("resize", resize);

    const energyFromLevels = (): number => {
      if (!activeRef.current) return 0;
      const data = sampleRef.current?.() ?? null;
      if (!data || data.length === 0) return 0;
      let sum = 0;
      for (let i = 0; i < data.length; i += 1) {
        const value = data[i] / 128 - 1;
        sum += value * value;
      }
      return Math.min(1, Math.sqrt(sum / data.length) * 4);
    };

    const render = () => {
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const half = Math.min(rect.width, rect.height) / 2;
      const energy = energyFromLevels();
      const baseRadius = half * 0.82 * (1 + energy * 0.12);

      const levels = activeRef.current ? (sampleRef.current?.() ?? null) : null;

      ctx.font = canvasFont;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const points: { x: number; y: number; z: number; char: string }[] = [];
      let sampleIndex = 0;

      for (let phi = 0; phi < Math.PI * 2; phi += 0.15) {
        for (let theta = 0; theta < Math.PI; theta += 0.15) {
          const x = Math.sin(theta) * Math.cos(phi + time * 0.5);
          const y = Math.sin(theta) * Math.sin(phi + time * 0.5);
          const z = Math.cos(theta);

          const rotY = time * 0.3;
          const newX = x * Math.cos(rotY) - z * Math.sin(rotY);
          const newZ = x * Math.sin(rotY) + z * Math.cos(rotY);

          const rotX = time * 0.2;
          const newY = y * Math.cos(rotX) - newZ * Math.sin(rotX);
          const finalZ = y * Math.sin(rotX) + newZ * Math.cos(rotX);

          let wave = 0;
          if (levels) {
            wave = levels[sampleIndex % levels.length] / 128 - 1;
            sampleIndex += 1;
          }
          const r = baseRadius * (1 + wave * energy * 0.12);

          const depth = Math.min(1, Math.max(0, (finalZ + 1) / 2));
          const charIndex = Math.min(
            chars.length - 1,
            Math.max(0, Math.floor(depth * (chars.length - 1))),
          );

          points.push({
            x: centerX + newX * r,
            y: centerY + newY * r,
            z: finalZ,
            char: chars[charIndex] ?? "·",
          });
        }
      }

      points.sort((a, b) => a.z - b.z);

      points.forEach((point) => {
        const depth = Math.min(1, Math.max(0, (point.z + 1) / 2));
        const alpha = 0.2 + depth * 0.8;
        ctx.fillStyle = `rgba(0, 0, 0, ${alpha})`;
        ctx.fillText(point.char, point.x, point.y);
      });

      time += 0.02 + energy * 0.06;
      frameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="block h-full w-full"
    />
  );
}
