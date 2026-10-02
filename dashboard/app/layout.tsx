import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'i9+ | Observatório da frota eletrificada',description:'Frota eletrificada brasileira, baterias e janelas estimadas com fontes auditáveis.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="pt-BR"><body>{children}</body></html>}
