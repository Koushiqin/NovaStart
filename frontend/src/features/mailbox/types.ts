// 与 backend/app/schemas/letter.py 对应（信箱页与结算②③共用同一契约，字段只此一份）

export type LetterStatus = "delivered" | "undelivered"

export interface Letter {
  id: number
  session_id: number | null
  content: string
  favorited: boolean
  handled: boolean
  status: LetterStatus
  focused_delivery: boolean
  sender_name: string | null
  expired_at: string
  created_at: string
}

export interface InboxResponse {
  letters: Letter[]
  server_time: string
}

export interface HistoryResponse {
  letters: Letter[]
  server_time: string
}

export interface OutboxLetter {
  id: number
  recipient_name: string | null
  content: string
  status: LetterStatus
  created_at: string
}

export interface OutboxResponse {
  letters: OutboxLetter[]
  server_time: string
}

export type SendResult = "delivered" | "rejected_full" | "rejected_unknown" | "already_sent"

export interface LetterSendResult {
  result: SendResult
  letter_id: number | null
  server_time: string
}
