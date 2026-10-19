import { useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useTransform,
  useReducedMotion,
} from "motion/react";
import type { MotionValue } from "motion/react";

export function RadiusValue({ value }: { value: MotionValue<number> }) {
  const reducedMotion = useReducedMotion();
  const [meters, setMeters] = useState(value.get());
  useMotionValueEvent(value, "change", (next) =>
    setMeters(Math.round(next / 100) * 100),
  );
  const text = (meters / 1000).toLocaleString("ru", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return (
    <span className="radius-counter">
      <span className="sr-only">{text} км</span>
      <span className="radius-counter-digits" aria-hidden="true">
        {[...text].map((character, index) =>
          /\d/.test(character) ? (
            <span className="radius-counter-column" key={text.length - index}>
              <AnimatePresence initial={false}>
                <motion.span
                  key={character}
                  className="radius-counter-digit"
                  initial={{
                    y: reducedMotion ? 0 : "-100%",
                    opacity: reducedMotion ? 1 : 0,
                  }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: reducedMotion ? 0 : "100%", opacity: 0 }}
                  transition={{
                    duration: reducedMotion ? 0 : 0.16,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                >
                  {character}
                </motion.span>
              </AnimatePresence>
            </span>
          ) : (
            <span key={text.length - index}>{character}</span>
          ),
        )}
        <span className="radius-counter-unit">км</span>
      </span>
    </span>
  );
}

export default function RadiusControl({
  radius,
  animated,
  onChange,
}: {
  radius: number;
  animated: MotionValue<number>;
  onChange: (radius: number) => void;
}) {
  const fraction = useTransform(animated, (value) =>
    Math.max(0, Math.min(1, (value - 500) / 9500)),
  );
  const position = useTransform(fraction, (value) => `${value * 100}%`);
  return (
    <div className="radius-control">
      <div className="radius-label">
        <label htmlFor="radius">Радиус поиска</label>
        <output htmlFor="radius" aria-live="off">
          <RadiusValue value={animated} />
        </output>
      </div>
      <div className="radius-slider">
        <div className="radius-slider-track" aria-hidden="true">
          <motion.div
            className="radius-slider-fill"
            style={{ scaleX: fraction }}
          />
          {[2, 4, 6, 8, 10].map((km) => (
            <span
              key={km}
              className="radius-slider-tick"
              style={{ left: `${((km - 0.5) / 9.5) * 100}%` }}
            />
          ))}
          <motion.div
            className="radius-slider-thumb"
            style={{ left: position }}
          />
        </div>
        <input
          id="radius"
          type="range"
          min="500"
          max="10000"
          step="500"
          value={radius}
          aria-valuetext={`${(radius / 1000).toLocaleString("ru")} км`}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>
      <div className="radius-slider-labels" aria-hidden="true">
        {[2, 4, 6, 8, 10].map((km) => (
          <span key={km} style={{ left: `${((km - 0.5) / 9.5) * 100}%` }}>
            {km.toLocaleString("ru")}
          </span>
        ))}
      </div>
    </div>
  );
}
