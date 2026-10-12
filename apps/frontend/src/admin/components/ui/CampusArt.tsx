// Photo hero (Dashboard campus, Admissions students, …): covers the banner and is positioned so the
// dome and full facade stay in view; a deep magenta → purple → indigo overlay sits
// behind the text on the left and blends into the photo.

import { asset } from '../../lib/assets';
import React from 'react';

/** Left-to-right overlays: the brand magenta/purple, or the Student Lifecycle violet. */
const OVERLAYS = {
  brand: 'linear-gradient(90deg,rgba(112,14,92,0.94) 0%,rgba(84,24,140,0.86) 30%,rgba(55,48,163,0.45) 52%,rgba(49,46,129,0.08) 70%,transparent 82%)',
  violet: 'linear-gradient(90deg,rgba(109,40,217,0.95) 0%,rgba(91,33,182,0.86) 30%,rgba(67,56,202,0.45) 52%,rgba(67,56,202,0.08) 70%,transparent 82%)'
} as const;

export const CampusPhoto: React.FC<{
  src?: string;
  position?: string;
  tone?: keyof typeof OVERLAYS;
  /** 'right': the photo fills only the right part of the hero and fades in over the page colour. */
  fit?: 'full' | 'right';
}> = ({ src = asset('/campus.jpg'), position = '62% 72%', tone = 'brand', fit = 'full' }) =>
  fit === 'right' ? (
    <div
      className="absolute inset-y-0 right-0 w-[64%] bg-cover bg-no-repeat [mask-image:linear-gradient(to_right,transparent_0%,black_35%)]"
      style={{ backgroundImage: `url('${src}')`, backgroundPosition: position }}
    />
  ) : (
  <>
    <div className="absolute inset-0 bg-cover bg-no-repeat" style={{ backgroundImage: `url('${src}')`, backgroundPosition: position }} />
    <div className="absolute inset-0" style={{ backgroundImage: OVERLAYS[tone] }} />
    <div className="absolute inset-x-0 bottom-0 h-1/2 bg-[linear-gradient(to_top,rgba(17,12,48,0.35),transparent)]" />
  </>
  );
