import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './admin.css';

// Click ripple for every button in the app
document.addEventListener('pointerdown', (e) => {
  const button = (e.target as HTMLElement).closest('button');
  if (!button || button.disabled) return;
  const rect = button.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  if (getComputedStyle(button).position === 'static') button.style.position = 'relative';
  button.style.overflow = 'hidden';
  const ripple = document.createElement('span');
  ripple.className = 'ripple';
  ripple.style.width = ripple.style.height = `${size}px`;
  ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
  ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
  button.appendChild(ripple);
  ripple.addEventListener('animationend', () => ripple.remove());
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
