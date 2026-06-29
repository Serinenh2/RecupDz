import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Bot, Send, MessageSquare, Plus, Trash2, X, Sparkles, Loader2, Minimize2, BookOpen
} from 'lucide-react'
import api from '../../api'
import toast from 'react-hot-toast'

const aiAPI = {
  getConversations:  ()         => api.get('/ai/conversations/'),
  createConversation:(data)     => api.post('/ai/conversations/', data),
  deleteConversation:(id)       => api.delete(`/ai/conversations/${id}/`),
  getMessages:       (convId)   => api.get(`/ai/messages/?conversation_id=${convId}`),
  sendMessage:       (convId, d)=> api.post(`/ai/conversations/${convId}/envoyer_message/`, d),
  getSuggestions:    ()         => api.get('/ai/conversations/suggestions/'),
}

function formatMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/^### (.+)$/gm, '<h3 class="font-bold text-xs mt-2 mb-0.5 text-slate-900 dark:text-white">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="font-bold text-sm mt-3 mb-1 text-slate-900 dark:text-white">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold text-slate-900 dark:text-white">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-slate-100 dark:bg-[#2B3D1E] rounded text-[10px] font-mono">$1</code>')
    .replace(/^- (.+)$/gm, '<li class="ml-3 text-xs text-slate-700 dark:text-slate-300 list-disc">$1</li>')
    .replace(/^✅ (.+)$/gm, '<p class="text-emerald-600 dark:text-emerald-400 text-xs font-semibold">✅ $1</p>')
    .replace(/^⚠️ (.+)$/gm, '<p class="text-amber-600 dark:text-amber-400 text-xs font-semibold">⚠️ $1</p>')
    .replace(/\n\n/g, '</p><p class="mt-1">')
    .replace(/\n/g, '<br/>')
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'USER'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`flex gap-2 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
        <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-gradient-to-br from-primary-500 to-primary-800 text-white'
        }`}>
          {isUser ? <MessageSquare size={10} /> : <Bot size={10} />}
        </div>
        <div className={`rounded-xl px-3 py-2 ${
          isUser
            ? 'bg-primary-600 text-white rounded-tr-sm'
            : 'bg-white dark:bg-[#16240D] border border-[#E2E8F0] dark:border-[#2B3D1E] text-slate-800 dark:text-slate-200 rounded-tl-sm shadow-sm'
        }`}>
          {isUser ? (
            <p className="text-xs leading-relaxed">{msg.message}</p>
          ) : (
            <div
              className="text-xs leading-relaxed prose prose-xs dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.message) }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function Suggestions({ onSelect }) {
  const [suggestions, setSuggestions] = useState([])
  useEffect(() => {
    aiAPI.getSuggestions().then(res => setSuggestions(res.data.suggestions || [])).catch(() => {})
  }, [])

  const glossaryQuick = [
    'Qu\'est-ce qu\'un BSD ?',
    'Définition : déchet dangereux',
    'Qu\'est-ce qu\'un agrément ?',
    'Principe pollueur-payeur',
  ]

  return (
    <div className="mb-2 w-full">
      <p className="text-[10px] font-bold text-slate-400 mb-1 flex items-center gap-1">
        <Sparkles size={10} /> Suggestions
      </p>
      <div className="flex flex-wrap gap-1 justify-center">
        {glossaryQuick.map((s, i) => (
          <button key={i} onClick={() => onSelect(s)}
            className="px-2 py-1 rounded-full text-[10px] font-medium bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-800 hover:bg-primary-100 transition-all">
            <BookOpen size={8} className="inline mr-0.5" />{s}
          </button>
        ))}
      </div>
      {suggestions.length > 0 && (
        <>
          <p className="text-[10px] font-bold text-slate-400 mt-2 mb-1 flex items-center gap-1">
            <Sparkles size={10} /> IA
          </p>
          <div className="flex flex-wrap gap-1 justify-center">
            {suggestions.slice(0, 3).map((s, i) => (
              <button key={i} onClick={() => onSelect(s)}
                className="px-2 py-1 rounded-full text-[10px] font-medium bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-700 hover:bg-primary-100 transition-all">
                {s}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default function AIAssistantPage() {
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const loadConversations = useCallback(async () => {
    try {
      const res = await aiAPI.getConversations()
      const data = res.data.results || res.data
      setConversations(Array.isArray(data) ? data : [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { if (open) loadConversations() }, [open, loadConversations])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const loadMessages = async (convId) => {
    setLoadingMessages(true)
    try {
      const res = await aiAPI.getMessages(convId)
      const data = res.data.results || res.data
      setMessages(Array.isArray(data) ? data : [])
    } catch {
      toast.error('Erreur chargement')
    }
    setLoadingMessages(false)
  }

  const handleSelectConv = (convId) => {
    setActiveConvId(convId)
    loadMessages(convId)
  }

  const handleNewConv = () => {
    setActiveConvId(null)
    setMessages([])
    inputRef.current?.focus()
  }

  const handleDeleteConv = async (convId) => {
    try {
      await aiAPI.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (activeConvId === convId) { setActiveConvId(null); setMessages([]) }
    } catch { /* ignore */ }
  }

  const handleSend = async (text) => {
    const msg = (text || input).trim()
    if (!msg || sending) return
    setInput('')
    setSending(true)
    const userMsg = { id: Date.now(), role: 'USER', message: msg }
    setMessages(prev => [...prev, userMsg])

    try {
      let convId = activeConvId
      if (!convId) {
        const res = await aiAPI.createConversation({
          titre: msg.slice(0, 50) + (msg.length > 50 ? '...' : ''),
          contexte: 'GENERAL',
        })
        convId = res.data.id
        setActiveConvId(convId)
        await loadConversations()
      }

      const res = await aiAPI.sendMessage(convId, { message: msg })
      const finalReply = res.data.reponse || ''

      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'ASSISTANT', message: finalReply }])
      if (!activeConvId) await loadConversations()
    } catch {
      setMessages(prev => prev.filter(m => m.id !== userMsg.id))
      toast.error("Erreur lors de l'envoi")
    }
    setSending(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <>
      {/* Floating chat button */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 hover:scale-110 ${
          open
            ? 'bg-slate-700 hover:bg-slate-600'
            : 'bg-gradient-to-br from-primary-600 to-primary-900 hover:from-primary-500 hover:to-primary-800'
        }`}
      >
        {open
          ? <Minimize2 size={22} className="text-white" />
          : <Bot size={24} className="text-white" />
        }
        {!open && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-white animate-pulse" />
        )}
      </button>

      {/* Chat window */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[380px] h-[540px] bg-[#F8FAFC] dark:bg-[#0D1B0A] rounded-2xl shadow-2xl border border-[#E2E8F0] dark:border-[#2B3D1E] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">

          {/* Header */}
          <div className="bg-gradient-to-r from-primary-600 to-primary-900 px-4 py-3 flex items-center gap-3 flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-white">Assistant IA</h3>
              <p className="text-[10px] text-white/70">Recup <span className="font-arabiya">نفاية</span> — Réglementation déchets</p>
            </div>
            <div className="flex gap-1">
              <button onClick={handleNewConv}
                className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                title="Nouvelle conversation">
                <Plus size={14} className="text-white" />
              </button>
              <button onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg hover:bg-white/20 transition-colors">
                <X size={14} className="text-white" />
              </button>
            </div>
          </div>

          {/* Conversation history mini-bar */}
          {conversations.length > 0 && (
            <div className="px-2 py-1.5 border-b border-[#E2E8F0] dark:border-[#2B3D1E] bg-white dark:bg-[#16240D] flex gap-1 overflow-x-auto flex-shrink-0">
              {conversations.slice(0, 5).map(c => (
                <button key={c.id} onClick={() => handleSelectConv(c.id)}
                  className={`px-2 py-1 rounded-lg text-[10px] font-semibold whitespace-nowrap transition-all flex-shrink-0 ${
                    activeConvId === c.id
                      ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                      : 'bg-slate-100 dark:bg-[#16240D] text-slate-500 hover:bg-slate-200 dark:hover:bg-[#2B3D1E]'
                  }`}>
                  {c.titre?.slice(0, 20) || 'Chat'}
                </button>
              ))}
            </div>
          )}

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-3">
            {loadingMessages ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 size={20} className="text-slate-400 animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full px-4">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-800 flex items-center justify-center mb-3 shadow-lg">
                  <Bot size={22} className="text-white" />
                </div>
                <p className="text-sm font-bold text-slate-700 dark:text-white mb-1 text-center">Bonjour !</p>
                <p className="text-[11px] text-slate-400 text-center mb-2">
                  Assistant IA réglementaire — Glossaire des déchets
                </p>
                <div className="flex flex-wrap gap-1 justify-center mb-3">
                  {['BSD', 'Agrément', 'Déchet dangereux', 'Recyclage', 'Loi 01-19'].map(t => (
                    <span key={t} className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300 border border-primary-200 dark:border-primary-800">
                      {t}
                    </span>
                  ))}
                </div>
                <Suggestions onSelect={handleSend} />
              </div>
            ) : (
              <>
                {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
                {sending && (
                  <div className="flex justify-start mb-2">
                    <div className="flex gap-2">
                      <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary-500 to-primary-800 flex items-center justify-center text-white flex-shrink-0">
                        <Bot size={10} />
                      </div>
                      <div className="bg-white dark:bg-[#16240D] border border-[#E2E8F0] dark:border-[#2B3D1E] rounded-xl rounded-tl-sm px-3 py-2 shadow-sm">
                        <div className="flex items-center gap-1.5">
                          <Loader2 size={12} className="text-primary-500 animate-spin" />
                          <span className="text-[11px] text-slate-500">Analyse...</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input area */}
          <div className="p-2.5 border-t border-[#E2E8F0] dark:border-[#2B3D1E] bg-white dark:bg-[#16240D] flex-shrink-0">
            <div className="flex items-end gap-1.5">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Votre question..."
                className="flex-1 resize-none min-h-[36px] max-h-[80px] text-xs px-3 py-2 rounded-xl border border-[#E2E8F0] dark:border-[#2B3D1E] bg-[#F8FAFC] dark:bg-[#0D1B0A] text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-400 transition-all"
                rows={1}
                disabled={sending}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || sending}
                className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-600 to-primary-800 flex items-center justify-center text-white flex-shrink-0 disabled:opacity-40 hover:from-primary-500 hover:to-primary-700 transition-all"
              >
                {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
