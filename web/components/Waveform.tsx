"use client";

import { useEffect, useRef } from "react";

interface Props {
  active: boolean;
  sample: () => Uint8Array | null;
}

/** Live oscilloscope drawn from the analyser node while recording. */
export function Waveform({ active, sample }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const { width, height } = canvas;
      context.clearRect(0, 0, width, height);

      const data = active ? sample() : null;
      context.lineWidth = 2;
      context.strokeStyle = active ? "#38bdf8" : "#334155";
      context.beginPath();

      if (!data) {
        context.moveTo(0, height / 2);
        context.lineTo(width, height / 2);
      } else {
        const step = width / data.length;
        for (let index = 0; index < data.length; index += 1) {
          const value = data[index] / 128 - 1;
          const y = height / 2 + (value * height) / 2;
          if (index === 0) context.moveTo(0, y);
          else context.lineTo(index * step, y);
        }
      }
      context.stroke();
    };

    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [active, sample]);

  return (
    <canvas
      ref={canvasRef}
      width={640}
      height={72}
      className="h-16 w-full rounded-lg bg-[var(--color-panel)]"
      aria-hidden
    />
  );
}
