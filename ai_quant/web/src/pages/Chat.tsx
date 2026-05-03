import { Card, CardBody, CardHeader } from '@/components/Card'

const STREAMLIT_URL = import.meta.env.VITE_STREAMLIT_CHAT_URL || 'http://localhost:8501'

export default function Chat() {
  return (
    <Card className="overflow-hidden">
      <CardHeader title="AI 对话机器人（Streamlit）" />
      <CardBody className="p-0">
        <iframe
          src={STREAMLIT_URL}
          title="AI Chat Streamlit"
          className="h-[78vh] w-full border-0"
          referrerPolicy="no-referrer"
        />
      </CardBody>
    </Card>
  )
}
