import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { sendChat } from '../api/client';

export default function Advisor({ setScreen }: { setScreen: (s: string) => void }) {
  const { sessionId, activeFarmId, profile, prefillQuestion, setPrefillQuestion } = useAppStore();
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatBoxRef = useRef<HTMLDivElement>(null);

  // اقتراحات جاهزة للمزارع (لتسهيل الاستخدام)
  const presets = [
    "هل الفحم الحيوي مناسب لمزرعتي؟",
    "ما الجرعة المناسبة للتربة الرملية؟",
    "هل يقلل الفحم من تبخر الماء؟",
    "هل يؤثر الفحم على ملوحة التربة؟"
  ];

  // التقاط السؤال القادم من صفحة الرصد
  useEffect(() => {
    if (prefillQuestion && !loading) {
      setInput(prefillQuestion);
      setPrefillQuestion(null);
    }
  }, [prefillQuestion, setPrefillQuestion, loading]);

  // التمرير التلقائي لأسفل المحادثة
  useEffect(() => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async (e?: React.FormEvent, presetText?: string) => {
    if (e) e.preventDefault();
    const msgToSend = presetText || input;
    if (!msgToSend.trim() || !sessionId || loading) return;

    const userMsg = msgToSend.trim();
    if (!presetText) setInput(''); // مسح الحقل فقط إذا لم يكن اقتراحاً
    
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
      {/* صندوق المحادثة */}
      <div className="card" style={{ flex: '2 1 520px', minWidth: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderBottom: '1px solid #E5DCCB' }}>
          <div style={{ fontWeight: 800, color: '#0B5D3B', fontSize: 18 }}>المرشد الزراعي الذكي</div>
          <button onClick={() => setMessages([])} className="btn2" style={{ minHeight: 36, padding: '0 16px', borderRadius: 12, fontSize: 14 }}>محادثة جديدة</button>
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
                
                {/* عرض المصادر العلمية */}
                {m.sources && m.sources.length > 0 && (
                  <div style={{ marginTop: 12, background: '#F8F1E2', border: '1px solid #E5DCCB', borderRadius: 10, padding: '6px 12px', fontSize: 13 }}>
                    <b>المصادر:</b> {m.sources.map((s: any) => s.title || s.record_id).join('، ')}
                  </div>
                )}
              </div>
              
              {/* زر الربط بوكيل الجمع (يظهر فقط بعد الإجابة الأخيرة) */}
              {m.role === 'bot' && i === messages.length - 1 && !m.isError && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                  <button 
                    className="btn" 
                    onClick={() => setScreen('collect')} 
                    style={{ fontSize: 15, background: '#C8A25A', color: '#1E2A25', display: 'flex', alignItems: 'center', gap: 8 }}
                  >
                    🚛 احجز موعد جمع السعف الآن
                  </button>
                </div>
              )}
            </div>
          ))}
          {loading && <div style={{ alignSelf: 'flex-end', color: '#55615A', fontStyle: 'italic' }}>جارٍ تحليل البيانات والبحث في الأبحاث...</div>}
        </div>

        {/* منطقة الإدخال والاقتراحات */}
        <div style={{ padding: '16px 24px 20px', borderTop: '1px solid #E5DCCB', background: '#FFFDF9' }}>
          
          {/* أزرار الاقتراحات لتسهيل الاستخدام */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
            {presets.map((p, idx) => (
              <button 
                key={idx} 
                onClick={() => handleSend(undefined, p)}
                disabled={loading}
                style={{ background: '#E6F2EC', color: '#0B5D3B', border: '1px solid #0B5D3B', padding: '6px 12px', borderRadius: 20, fontSize: 13, cursor: 'pointer' }}
              >
                {p}
              </button>
            ))}
          </div>

          <form onSubmit={handleSend} style={{ display: 'flex', gap: 10 }}>
            <input
              className="fld"
              type="text"
              placeholder="اكتب سؤالك للمرشد هنا…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              style={{ flex: 1, minWidth: 0, borderRadius: 999, background: '#F7F3EA' }}
            />
            <button 
              type="submit" 
              disabled={loading || !input.trim()}
              className="btn"
              style={{ flex: '0 0 auto', minHeight: 48, padding: '0 28px', borderRadius: 999, background: loading ? '#9AA59F' : '#0B5D3B' }}
            >
              {loading ? '...' : 'إرسال'}
            </button>
          </form>
        </div>
      </div>

      {/* القائمة الجانبية (بيانات المزرعة) */}
      <aside style={{ flex: '1 1 260px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 800, marginBottom: 12, color: '#0B5D3B' }}>بيانات مزرعتك الحالية</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 15 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F0F0F0', paddingBottom: 4 }}><span style={{ color: '#55615A' }}>التربة</span><b>{profile.soil}</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F0F0F0', paddingBottom: 4 }}><span style={{ color: '#55615A' }}>حموضة التربة (pH)</span><b>{profile.ph}</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F0F0F0', paddingBottom: 4 }}><span style={{ color: '#55615A' }}>نظام الري</span><b>{profile.irr}</b></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: '#55615A' }}>عدد النخيل</span><b>{profile.palms} نخلة</b></div>
          </div>
        </div>
        <div style={{ background: '#F8F1E2', border: '1px solid #C8A25A', borderRadius: 20, padding: '16px 20px', fontSize: 13.5, lineHeight: 1.6 }}>
          <b>ملاحظة:</b> كل الأرقام والنتائج مستندة إلى أبحاث علمية محكمة (مثل جامعة الملك سعود). المرشد لا يقدم وعوداً بلا دليل.
        </div>
      </aside>
    </div>
  );
}