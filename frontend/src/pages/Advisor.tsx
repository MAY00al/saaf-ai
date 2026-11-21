import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { sendChat } from '../api/client';

export default function Advisor() {
  const { sessionId, activeFarmId } = useAppStore();
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const data = await sendChat(sessionId, userMsg, activeFarmId || undefined);
      
      let botText = data.answer_ar || 'لم يتم العثور على إجابة.';
      if (data.status === 'insufficient_evidence') {
        botText = 'عذراً، لا توجد أدلة كافية في قاعدة البيانات للإجابة على هذا السؤال.';
      } else if (data.status === 'unavailable') {
        botText = 'خدمة الذكاء الاصطناعي غير متاحة حالياً.';
      }

      setMessages((prev) => [
        ...prev,
        { 
          role: 'bot', 
          text: botText, 
          sources: data.recommendation?.sources || [],
          simulated: data.recommendation?.simulated_data 
        }
      ]);
    } catch (err: any) {
      const errorMsg = err?.error?.message_ar || 'تعذر الاتصال بالمرشد. تأكد من تشغيل الخادم.';
      setMessages((prev) => [...prev, { role: 'bot', text: errorMsg, isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      <div className="card" style={{ flex: '2 1 520px', minWidth: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 20px', borderBottom: '1px solid #E5DCCB' }}>
          <button onClick={() => setMessages([])} className="btn2" style={{ minHeight: 40, padding: '0 18px', borderRadius: 12, fontSize: 14.5 }}>محادثة جديدة</button>
        </div>
        
        <div ref={chatBoxRef} style={{ background: '#F7F3EA', padding: '20px 24px', minHeight: 360, maxHeight: 480, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', color: '#55615A', marginTop: 40 }}>
              مرحباً! أنا مرشد سعف. اسألني عن أرضك أو الفحم الحيوي.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-start' : 'flex-end', maxWidth: '85%' }}>
              <div style={{
                background: m.role === 'user' ? '#0B5D3B' : m.isError ? '#FDECEC' : '#FFFDF9',
                color: m.role === 'user' ? '#FFFFFF' : m.isError ? '#8E1C1C' : '#1E2A25',
                border: m.role === 'bot' && !m.isError ? '1px solid #E5DCCB' : 'none',
                borderRadius: m.role === 'user' ? '18px 18px 18px 4px' : '18px 18px 4px 18px',
                padding: '12px 18px',
                fontSize: 16,
                whiteSpace: 'pre-line'
              }}>
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div style={{ marginTop: 12, background: '#F8F1E2', border: '1px solid #E5DCCB', borderRadius: 10, padding: '4px 12px', fontSize: 13 }}>
                    المصادر: {m.sources.map((s: any) => s.title || s.record_id).join('، ')}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && <div style={{ alignSelf: 'flex-end', color: '#55615A' }}>جارٍ التفكير...</div>}
        </div>

        <div style={{ padding: '16px 24px 20px', borderTop: '1px solid #E5DCCB' }}>
          <form onSubmit={handleSend} style={{ display: 'flex', gap: 10 }}>
            <input
              className="fld"
              type="text"
              placeholder="اسأل عن أرضك أو زراعتك…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              style={{ flex: 1, minWidth: 0, borderRadius: 999, background: '#FFFFFF' }}
            />
            <button 
              type="submit" 
              disabled={loading || !input.trim()}
              className="btn"
              style={{ flex: '0 0 auto', minHeight: 48, padding: '0 28px', borderRadius: 999, background: loading ? '#9AA59F' : '#0B5D3B' }}
            >
              {loading ? 'جارٍ الرد…' : 'إرسال'}
            </button>
          </form>
        </div>
      </div>

      <aside style={{ flex: '1 1 260px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>ما يعرفه المرشد عن مزرعتك</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 15 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: '#55615A' }}>التربة</span><b>رملية</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: '#55615A' }}>pH</span><b>7.4</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: '#55615A' }}>الري</span><b>تنقيط</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: '#55615A' }}>النخيل</span><b>350 نخلة</b></div>
          </div>
        </div>
        <div style={{ background: '#F8F1E2', border: '1px solid #C8A25A', borderRadius: 20, padding: '16px 20px', fontSize: 14 }}>
          كل الأرقام من تجارب مخبرية وصوبات زراعية أو تحليلات بحثية، وليست قياسًا ميدانيًا مضمونًا في مزرعتك.
        </div>
      </aside>
    </div>
  );
}