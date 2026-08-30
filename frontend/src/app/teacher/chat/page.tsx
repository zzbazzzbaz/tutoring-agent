import { ChatView } from "@/components/chat/ChatView";

export const dynamic = "force-dynamic";

export default function TeacherChatPage() {
  return <ChatView role="teacher" />;
}
