import { Link } from 'react-router-dom'
import { Card, CardBody } from '@/components/Card'

export default function NotFound() {
  return (
    <Card>
      <CardBody className="px-6 py-10 text-center">
        <div className="text-lg font-semibold text-zinc-900">页面不存在</div>
        <div className="mt-2 text-sm text-zinc-600">
          <Link to="/" className="text-zinc-900 underline">
            返回订单审批
          </Link>
        </div>
      </CardBody>
    </Card>
  )
}
