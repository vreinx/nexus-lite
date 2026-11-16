// Tests de componentes: se renderizan en un DOM simulado (jsdom) con el
// estado compartido `fleet` preparado a mano, sin backend.
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';
import { fleet } from '../lib/fleet.svelte.js';
import ConnectionBadge from './ConnectionBadge.svelte';
import MissionPopover from './MissionPopover.svelte';

const MAP = {
  grid: { width: 20, height: 12 },
  simulation: { drop_clear_seconds: 2 },
  stations: [
    { id: 'P1', type: 'PICKUP', x: 0, y: 1 },
    { id: 'D1', type: 'DROP', x: 19, y: 3 },
    { id: 'D2', type: 'DROP', x: 19, y: 8 },
  ],
};
const P1 = MAP.stations[0];

afterEach(() => cleanup());

describe('ConnectionBadge (F-04)', () => {
  it('en vivo', () => {
    fleet.connection = 'online';
    render(ConnectionBadge);
    expect(screen.getByText('En vivo')).toBeTruthy();
    expect(screen.queryByText('Reintentar ya')).toBeNull();
  });
  it('sin conexión muestra la cuenta atrás y el botón de reintentar', () => {
    fleet.connection = 'offline';
    fleet.retryIn = 4;
    render(ConnectionBadge);
    expect(screen.getByText('Sin conexión')).toBeTruthy();
    expect(screen.getByText(/reintento en 4 s/)).toBeTruthy();
    expect(screen.getByText('Reintentar ya')).toBeTruthy();
  });
});

describe('MissionPopover: palets', () => {
  it('origen sin palet: solo ofrece declararlo', () => {
    fleet.map = MAP;
    fleet.stations = { P1: { id: 'P1', pallet: false } };
    render(MissionPopover, { station: P1, onclose: () => {} });
    expect(screen.getByText('Declarar palet')).toBeTruthy();
    expect(screen.queryByText(/Crear P1/)).toBeNull();
  });
  it('palet ya asignado a una orden: avisa y no deja crear otra', () => {
    fleet.map = MAP;
    fleet.stations = { P1: { id: 'P1', pallet: true, reserved_by: 'abcd1234-xxxx' } };
    render(MissionPopover, { station: P1, onclose: () => {} });
    expect(screen.getByText(/ya tiene una orden asignada/)).toBeTruthy();
    expect(screen.queryByText(/Crear P1/)).toBeNull();
  });
  it('con palet libre: destinos, retirar palet y destino ocupado marcado', () => {
    fleet.map = MAP;
    fleet.stations = { P1: { id: 'P1', pallet: true }, D2: { id: 'D2', pallet: true, clears_in: 2 } };
    render(MissionPopover, { station: P1, onclose: () => {} });
    expect(screen.getByText(/Crear P1 → D1/)).toBeTruthy();
    expect(screen.getByText('Retirar palet')).toBeTruthy();
    expect(screen.getByText(/ocupado/)).toBeTruthy();   // D2 aún tiene el palet entregado
  });
});
