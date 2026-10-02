import {BatteryPage} from '../../veiculos/fleet-ui';export default async function Page({params}:{params:Promise<{id:string}>}){return <BatteryPage id={(await params).id}/>}
