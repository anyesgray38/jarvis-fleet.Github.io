import { notFound } from 'next/navigation'
import AgentSiteDashboard from '../../components/AgentSiteDashboard'
import { getAgentSite } from '../../../lib/agent-sites'

export const dynamic = 'force-dynamic'

export default async function AgentSitePage({ params }: { params: Promise<{ agent: string }> }) {
  const { agent } = await params
  const site = getAgentSite(agent)
  if (!site) notFound()
  return <AgentSiteDashboard site={site} />
}
