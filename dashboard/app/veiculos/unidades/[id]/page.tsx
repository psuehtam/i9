import {VehiclePage} from '../../fleet-ui';export default async function Page({params}:{params:Promise<{id:string}>}){return <VehiclePage id={(await params).id}/>}
