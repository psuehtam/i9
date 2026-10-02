import {ModelPage} from '../../fleet-ui';export default async function Page({params}:{params:Promise<{id:string}>}){return <ModelPage id={(await params).id}/>}
