export interface RestaurantLocation {
  id: string;
  nombre: string;
  ciudad: string;
  pais: string;
  moneda: string;
  esActivo: boolean;
}

/**
 * Configuración temporal del módulo de inventario.
 * Restringido a las sedes con datos activos y sembrados en el backend (MED-001 y MIA-001).
 * NOTA: Esta lista estática debe ser reemplazada cuando exista un endpoint
 * oficial de consulta de sedes/locales en el backend.
 */
export const RESTAURANT_LOCATIONS: RestaurantLocation[] = [
  {
    id: "MED-001",
    nombre: "Brasaland El Poblado",
    ciudad: "Medellín",
    pais: "Colombia",
    moneda: "COP",
    esActivo: true,
  },
  {
    id: "MIA-001",
    nombre: "Brasaland Miami Downtown",
    ciudad: "Miami",
    pais: "USA",
    moneda: "USD",
    esActivo: true,
  },
];

export const DEFAULT_RESTAURANT_ID = "MED-001";
export const RESTAURANT_STORAGE_KEY = "brasaland_inventory_restaurant";

export function getRestaurantById(id: string): RestaurantLocation | undefined {
  return RESTAURANT_LOCATIONS.find((r) => r.id === id);
}

export function getRestaurantLabel(id: string): string {
  const r = getRestaurantById(id);
  if (!r) return id;
  return `${r.nombre} (${r.id})`;
}

export function isValidRestaurantId(id: string): boolean {
  return RESTAURANT_LOCATIONS.some((r) => r.id === id);
}
