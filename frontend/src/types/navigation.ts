export type ActiveTab = 'dashboard' | 'intelligence' | 'portfolio' | 'stress_testing';

export interface TabItem {
  id: ActiveTab;
  label: string;
  badge?: string | number;
}
