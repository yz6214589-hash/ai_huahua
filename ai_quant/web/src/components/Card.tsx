import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  onClick?: () => void
}

interface CardHeaderProps {
  children?: ReactNode
  title?: string
  subtitle?: string
  right?: ReactNode
  className?: string
}

interface CardBodyProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div className={`bg-white rounded-lg shadow ${className}`} onClick={onClick}>
      {children}
    </div>
  )
}

export function CardHeader({ children, title, subtitle, right, className = '' }: CardHeaderProps) {
  return (
    <div className={`px-6 py-4 border-b border-gray-200 ${className}`}>
      {title ? (
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">{title}</h3>
            {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
          </div>
          {right}
        </div>
      ) : (
        children
      )}
    </div>
  )
}

export function CardBody({ children, className = '' }: CardBodyProps) {
  return (
    <div className={`px-6 py-4 ${className}`}>
      {children}
    </div>
  )
}
