import {Car,Database,FileBarChart,Settings} from 'lucide-react';

export default function OperationalHeader({active}:{active:'vehicles'|'reports'|'data'|'admin'}){
 const links=[{id:'vehicles',href:'/veiculos',label:'Veículos',icon:Car},{id:'reports',href:'/frota',label:'Relatórios',icon:FileBarChart},{id:'data',href:'/inteligencia?area=dados',label:'Dados e atualização',icon:Database},{id:'admin',href:'/inteligencia?area=admin',label:'Administração',icon:Settings}];
 return <header className="fleet-header"><a className="fleet-logo" href="/veiculos" aria-label="i9+ — veículos">i9<span>+</span></a><nav aria-label="Navegação principal">{links.map(item=>{const Icon=item.icon;return <a key={item.id} className={active===item.id?'active':''} href={item.href}><Icon size={18}/>{item.label}</a>})}</nav></header>
}
