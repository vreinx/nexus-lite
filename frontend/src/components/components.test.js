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

import LoginView from './LoginView.svelte';
import MissionPanel from './MissionPanel.svelte';

describe('Inicio de sesión y roles', () => {
  it('la pantalla de login explica los dos usuarios y sus roles', () => {
    render(LoginView, { onlogin: () => {} });
    expect(screen.getByText('Iniciar sesión')).toBeTruthy();
    expect(screen.getByText('operador / operador')).toBeTruthy();
    expect(screen.getByText('consulta / consulta')).toBeTruthy();
  });
  it('operador: ve el formulario para crear órdenes', () => {
    fleet.map = MAP;
    fleet.user = { username: 'operador', role: 'OPERATOR', display_name: 'Operador' };
    render(MissionPanel);
    expect(screen.getByText('Nueva misión')).toBeTruthy();
  });
  it('consulta: no puede crear ni cancelar órdenes', () => {
    fleet.map = MAP;
    fleet.user = { username: 'consulta', role: 'VIEWER', display_name: 'Consulta' };
    fleet.missions = {
      m1: { id: 'm1aaaaaa', origin: 'P1', destination: 'D1', priority: 1, state: 'PENDING',
            created_at: '2026-11-16T10:00:00Z', robot_id: null },
    };
    render(MissionPanel);
    expect(screen.queryByText('Nueva misión')).toBeNull();
    expect(screen.getByText('Rol de consulta')).toBeTruthy();
    expect(screen.queryByText('Cancelar')).toBeNull();     // ve la orden pero sin botón
    expect(screen.getByText(/P1 → D1/)).toBeTruthy();
  });
});
