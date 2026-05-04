import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Provide a working localStorage for jsdom environment
const store = {};
const mockStorage = {
  getItem: (key) => store[key] ?? null,
  setItem: (key, value) => { store[key] = String(value); },
  removeItem: (key) => { delete store[key]; },
  clear: () => { Object.keys(store).forEach(k => delete store[k]); },
  get length() { return Object.keys(store).length; },
  key: (i) => Object.keys(store)[i] ?? null,
};
Object.defineProperty(globalThis, 'localStorage', { value: mockStorage, writable: true });

// Mock scrollIntoView for jsdom (not implemented in jsdom)
Element.prototype.scrollIntoView = vi.fn();
