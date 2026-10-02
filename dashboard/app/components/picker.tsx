'use client';
import {Select, SelectContent, SelectItem, SelectTrigger} from '@/components/ui/select';
import {month} from '../lib/format';

export function Picker({
  label,
  value,
  options,
  onChange,
  format,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  format?: (v: string) => string;
}) {
  const display = format || ((v: string) => (label === 'Referência mensal' ? month(v) : v));
  return (
    <div className="filter">
      <span>{label}</span>
      <Select items={[{value: '__all', label: 'Todos'}, ...options.map((v) => ({value: v, label: display(v)}))]} value={value || '__all'} onValueChange={(v) => onChange(v === '__all' ? '' : String(v))}>
        <SelectTrigger aria-label={label}>
          <span data-slot="select-value">{value && value !== '__all' ? display(value) : 'Todos'}</span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__all">Todos</SelectItem>
          {options.map((v) => (
            <SelectItem key={v} value={v}>
              {display(v)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
