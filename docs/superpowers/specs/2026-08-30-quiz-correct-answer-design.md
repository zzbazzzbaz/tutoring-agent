# Quiz 工具增加 correct_answer 参数设计

日期:2026-08-30
状态:已确认

## 背景

`present_question` HITL 工具通过 `interrupt()` 展示题目等待作答,学生提交后由 LLM 自行评估反馈。目前正确答案只存在于 LLM 反馈文本中,前端没有结构化数据可用来在作答后展示正确答案。

## 设计

### 后端 `services/agent_server`

1. **`src/teaching_agent/tools/schemas.py`**:`PresentQuestionArgs` 增加 `correct_answer: str` 字段:
   - 单选/多选:正确选项的完整文本,多选用 `", "` 连接,须与 `options` 中的文本完全一致
   - 简答题:参考答案要点
2. **`src/teaching_agent/tools/quiz.py`**:interrupt payload **不含** `correct_answer`(作答前绝不可见,防作弊);工具函数签名同步增加参数。
3. **`src/teaching_agent/agent/prompts.py`**:更新出题规则——LLM 出题时必须同时给出正确答案并自检(选项唯一无歧义);评估反馈时基于 `correct_answer` 判题,答错给出解析。

### 前端 `frontend`

4. **`src/components/chat/thread/messages/ai.tsx`**:`AnsweredQuizCard` 增加 `correctAnswer` prop,取自 `quizToolCall.args?.correct_answer`(与现有 topic/stem/options 读取方式一致)。
5. **`src/components/chat/thread/messages/answered-quiz-card.tsx`**:提交后展示:
   - 选择题:正确选项高亮标记"正确答案"(答对/答错均有)
   - 简答题:显示"参考答案"要点
6. 前端 `isQuizInterrupt` 校验不要求该字段,作答前的 interrupt 卡片不受影响。

## 安全约束

`correct_answer` 只存在于 tool_call args 和 `AnsweredQuizCard`(提交后渲染),作答前的 interrupt 卡片永远拿不到它。

## 数据流

- 出题:LLM 调用 `present_question(topic, q_type, stem, options, correct_answer)` → interrupt payload 仅含题目(无答案) → 前端 QuizInterruptView 作答
- 提交后:tool result 出现 → `ai.tsx` 从 tool_call args 读 `correct_answer` → `AnsweredQuizCard` 高亮正确答案 / 显示参考答案

## 测试

- 后端:interrupt payload 不含 `correct_answer`;工具返回正常
- 前端:构建通过;作答前不显示答案,提交后显示正确答案