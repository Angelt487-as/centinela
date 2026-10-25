import { createContext, useContext } from 'react';
import type { Dataset, Overview, Resource } from './types';
export const AppContext = createContext<{ datasets: Dataset[]; resources: Resource[]; overview: Overview | null; activeId: string; selectDataset: (id: string) => void; refresh: () => void; revision: number }>({ datasets: [], resources: [], overview: null, activeId: '', selectDataset: () => {}, refresh: () => {}, revision: 0 });
export const useWorkspace = () => useContext(AppContext);
