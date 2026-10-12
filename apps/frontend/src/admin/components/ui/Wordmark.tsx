// Education OS brand: the emblem (cap over an open book) plus the "EDUCATION OS"
// wordmark — heavy navy EDUCATION, OS in an orange-to-red gradient.

import { asset } from '../../lib/assets';
import React from 'react';

const WORDMARK_FONT = "font-['Montserrat','Inter',sans-serif] font-black";

/** Logo emblem without the wordmark. */
export const EduMark: React.FC<{ size?: number }> = ({ size = 36 }) => (
  <img src={asset('/eos-emblem.png')} alt="" aria-hidden className="flex-shrink-0 object-contain" style={{ width: size, height: size }} />
);

export const Wordmark: React.FC<{ className?: string; /** White "EDUCATION" for dark or photo backgrounds. */ inverse?: boolean }> = ({
  className = 'text-[19px]',
  inverse = false
}) => (
  <span className={`${WORDMARK_FONT} uppercase leading-none tracking-[-0.02em] whitespace-nowrap ${className}`} aria-label="Education OS">
    <span className={inverse ? 'text-white' : 'text-[#001E57]'}>Education</span>{' '}
    <span className="bg-[linear-gradient(135deg,#FD8305_0%,#FB6406_45%,#E0073F_100%)] bg-clip-text text-transparent">OS</span>
  </span>
);
