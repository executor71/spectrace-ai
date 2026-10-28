export type RequirementExample = { id: number; title: string; description: string }

// Synthetic rules and API contracts: knowledge/documents/{loan-rules,loan-api,
// asset-lifecycle,asset-api,return-rules,return-api,error-codes}.md
export const requirementExamples: readonly RequirementExample[] = [
  {
    id: 1,
    title: '부서장 대여 승인 및 자기 승인 금지 검증',
    description: '요청자 소속 부서의 부서장만 대여 신청을 승인할 수 있다.\n\n대여 신청자가 본인의 신청을 직접 승인하는 것은 허용하지 않는다.\n\n승인 권한이 없는 사용자의 요청은 거부되어야 한다.\n\n동일 자산에 대한 중복 승인도 허용하지 않는다.',
  },
  {
    id: 2,
    title: '자산 상태에 따른 대여 승인 제한',
    description: '대여 신청을 승인할 때 자산의 최신 상태와 신청 상태를 같은 트랜잭션에서 확인해야 한다.\n\nAVAILABLE 상태의 자산만 승인할 수 있다.\n\n이미 예약되었거나 대여 중인 자산 등 대여 불가능한 자산의 승인은 ASSET_NOT_AVAILABLE 오류로 거부한다.\n\n사용자에게 최신 재고를 조회하고 다른 장비를 선택하도록 안내한다.',
  },
  {
    id: 3,
    title: '대여 자산 반납 및 상태 변경 검증',
    description: '현재 대여자 또는 자산 담당자만 대여 자산의 반납을 접수할 수 있다.\n\n반납 접수 시 INSPECTION_PENDING 상태로 생성하며 접수만으로 자산을 AVAILABLE로 변경하지 않는다.\n\n같은 대여에 반납 접수가 이미 있으면 RETURN_ALREADY_REQUESTED 오류로 거부하고 새 반납 건을 생성하지 않는다.\n\n자산 담당자의 검사 결과가 PASSED이면 자산을 AVAILABLE로, DAMAGED이면 MAINTENANCE로 변경한다.',
  },
  {
    id: 4,
    title: 'IT 자산 등록 권한 및 필수값 검증',
    description: '자산 등록은 자산 관리자만 수행할 수 있다.\n\n등록 요청은 assetNumber, serialNumber, assetType, purchasedAt, departmentId를 사용하며 필수값 누락은 VALIDATION_ERROR로 거부한다.\n\n자산번호 또는 제조사 일련번호가 중복되면 DUPLICATE_ASSET 오류로 거부한다.\n\n정상 등록 시 HTTP 201과 생성된 자산의 위치를 반환하며 신규 자산 상태는 AVAILABLE이다.',
  },
  {
    id: 5,
    title: '대여 승인 요청 중복 처리 방지',
    description: '이미 승인되었거나 취소된 대여 신청을 다시 승인하면 LOAN_STATE_CONFLICT 상태 충돌 오류를 반환한다.\n\n승인만으로 자산을 ON_LOAN으로 바꾸거나 활성 대여를 시작하지 않으며, 담당자의 실물 지급 확인 후 활성 대여를 시작한다.\n\n요청자 소속 부서의 부서장만 승인할 수 있고 본인의 신청은 승인할 수 없다.\n\n승인 권한이 없는 요청을 거부하며 신청 및 자산 상태를 변경하지 않는다.',
  },
]

export function selectRandomExample(currentId?: number, random: () => number = Math.random): RequirementExample {
  const candidates = requirementExamples.filter(example => example.id !== currentId)
  return candidates[Math.floor(random() * candidates.length)]
}

export function needsExampleReplacementConfirmation(title: string, description: string, previous: RequirementExample | null): boolean {
  if (!title && !description) return false
  return !previous || title !== previous.title || description !== previous.description
}
