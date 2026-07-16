import Link from 'next/link'
import { Box, Card, Heading, Separator, Text } from '@radix-ui/themes'
import { api, type EmailMessage } from '@/lib/api'
import { EmailMessageControls } from '@/components/EmailMessageControls'

export const dynamic = 'force-dynamic'

export default async function EmailMessagePage({ params }: { params: Promise<{ messageId: string }> }) {
  const { messageId } = await params
  let message: EmailMessage | null = null
  try { message = await api.emailMessages.get(messageId) } catch { /* message absent */ }
  if (!message) return <Box><Heading size="5">Message introuvable</Heading><Link href="/inbox">Retour a la boite de reception</Link></Box>
  return <Box>
    <Link href="/inbox">Retour a la boite de reception</Link>
    <Heading size="6" mt="3">{message.subject || '(sans objet)'}</Heading>
    <Text as="p" color="gray" mt="2">De : {message.sender}<br />A : {message.recipient}<br />Recu : {new Date(message.received_at).toLocaleString('fr-FR')}</Text>
    <Box mt="3"><EmailMessageControls messageId={message.id} unread={!message.read_at} /></Box>
    <Separator size="4" my="4" />
    <Card><pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>{message.body_plain || 'Aucun contenu texte.'}</pre></Card>
    {message.body_html && <Box mt="4"><Heading size="3" mb="2">Version HTML</Heading><iframe title="Version HTML du message" sandbox="" srcDoc={message.body_html} style={{ width: '100%', minHeight: 420, border: '1px solid var(--gray-a6)' }} /></Box>}
  </Box>
}
