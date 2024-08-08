import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <main className="welcome">
    <p className="eyebrow">Keel / Action control</p>
    <h1>Every action,<br />accounted for.</h1>
    <p>Request tools, review exact arguments and follow each action through to its execution record.</p>
  </main>,
);
