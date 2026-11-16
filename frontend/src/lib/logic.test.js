import { describe, expect, it } from 'vitest';
import { batteryColor, batteryPath, formatDuration, missionQuery, nextHeading, routeCells } from './logic.js';

describe('batteryColor', () => {
  it('rojo por debajo del 20 %, ámbar hasta el 30 % y verde por encima', () => {
    expect(batteryColor(19.5)).toBe('#d1495b');
    expect(batteryColor(25)).toBe('#e0a458');
    expect(batteryColor(30)).toBe('#6ca087');
  });
});

describe('nextHeading', () => {
  it('mira hacia su siguiente celda de la ruta', () => {
    expect(nextHeading(0, { x: 3, y: 3, path: [[3, 4]] })).toBe(90);   // abajo
    const izq = nextHeading(0, { x: 3, y: 3, path: [[2, 3]] });          // izquierda
    expect(((izq % 360) + 360) % 360).toBe(180);  // ±180° es lo mismo: media vuelta
  });
  it('gira por el camino más corto (de 350° a 0° son +10°, no -350°)', () => {
    expect(nextHeading(350, { x: 0, y: 0, path: [[1, 0]] })).toBe(360);
    expect(nextHeading(-90, { x: 0, y: 5, path: [[0, 4]] })).toBe(-90);
  });
  it('parado conserva la orientación', () => {
    expect(nextHeading(45, { x: 0, y: 0, target: null })).toBe(45);
  });
});

describe('routeCells', () => {
  it('usa la ruta A* del backend', () => {
    const r = { x: 0, y: 0, target: [2, 0], path: [[0, 1], [1, 1], [2, 1], [2, 0]] };
    expect(routeCells(r)).toEqual([[0, 0], [0, 1], [1, 1], [2, 1], [2, 0]]);
  });
  it('sin ruta dibuja la L (primero X y luego Y); sin destino, nada', () => {
    expect(routeCells({ x: 0, y: 0, target: [3, 2] })).toEqual([[0, 0], [3, 0], [3, 2]]);
    expect(routeCells({ x: 0, y: 0, target: null })).toEqual([]);
  });
});

describe('missionQuery', () => {
  it('varios estados, solo filtros con valor y paginación', () => {
    const q = missionQuery({ states: ['DONE', 'FAILED'], robot_id: 'R1', origin: '', priority: '2' }, 25, 50);
    expect(q.getAll('state')).toEqual(['DONE', 'FAILED']);
    expect(q.get('robot_id')).toBe('R1');
    expect(q.has('origin')).toBe(false);
    expect(q.get('priority')).toBe('2');
    expect(q.get('limit')).toBe('25');
    expect(q.get('offset')).toBe('50');
  });
  it('las fechas locales se envían en ISO UTC', () => {
    const q = missionQuery({ created_from: '2026-11-15T10:00' }, 25, 0);
    expect(q.get('created_from')).toBe(new Date('2026-11-15T10:00').toISOString());
  });
});

describe('formatDuration', () => {
  const base = { created_at: '2026-11-15T10:00:00Z' };
  it('segundos y minutos', () => {
    expect(formatDuration({ ...base, state: 'DONE', updated_at: '2026-11-15T10:00:42Z' })).toBe('42 s');
    expect(formatDuration({ ...base, state: 'DONE', updated_at: '2026-11-15T10:01:12Z' })).toBe('1 min 12 s');
  });
  it('las órdenes activas no tienen duración', () => {
    expect(formatDuration({ ...base, state: 'ASSIGNED', updated_at: '2026-11-15T10:00:42Z' })).toBe('—');
  });
});

describe('batteryPath', () => {
  it('eje Y fijo 0-100 % y X proporcional al tiempo', () => {
    const pts = [
      { time: '2026-11-15T10:00:00Z', battery: 100 },
      { time: '2026-11-15T10:00:10Z', battery: 50 },
    ];
    const { line, area } = batteryPath(pts, 200, 100);
    expect(line).toBe('M0.0,0.0 L200.0,50.0');
    expect(area.endsWith('L200.0,100 L0.0,100 Z')).toBe(true);
  });
  it('sin datos no dibuja nada', () => {
    expect(batteryPath([], 200, 100)).toEqual({ line: '', area: '' });
  });
});
