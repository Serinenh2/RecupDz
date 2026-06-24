import axios from 'axios'
const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(cfg => {
  const t = localStorage.getItem('access_token')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
api.interceptors.response.use(r => r, async e => {
  if (e.response?.status === 401 && !e.config._retry) {
    const ref = localStorage.getItem('refresh_token')
    if (ref) {
      try {
        e.config._retry = true
        const { data } = await axios.post('/api/auth/token/refresh/', { refresh: ref })
        localStorage.setItem('access_token', data.access)
        e.config.headers.Authorization = `Bearer ${data.access}`
        return api(e.config)
      } catch {
        localStorage.clear()
        window.location.href = '/login'
      }
    } else {
      localStorage.clear()
      window.location.href = '/login'
    }
  }
  return Promise.reject(e)
})
export default api

export const recuperateursAPI = {
  getAll:  (p) => api.get('/recuperateurs/', { params: p }),
  get:     (id)=> api.get(`/recuperateurs/${id}/`),
  create:  (d) => api.post('/recuperateurs/', d),
  update:  (id,d)=> api.patch(`/recuperateurs/${id}/`, d),
  delete:  (id)=> api.delete(`/recuperateurs/${id}/`),
  stats:   ()  => api.get('/recuperateurs/stats/'),
  alerts:  ()  => api.get('/recuperateurs/alerts/'),
}
export const nomenclatureAPI = {
  getAll:  (p) => api.get('/nomenclature/', { params: p }),
}
export const traceabilityAPI = {
  getAll:  (p) => api.get('/traceability/', { params: p }),
  get:     (id)=> api.get(`/traceability/${id}/`),
  create:  (d) => api.post('/traceability/', d),
  update:  (id,d)=> api.patch(`/traceability/${id}/`, d),
  delete:  (id)=> api.delete(`/traceability/${id}/`),
  stats:   ()  => api.get('/traceability/stats/'),
}
export const bsdAPI = {
  getAll:  (p) => api.get('/bsd/', { params: p }),
  get:     (id)=> api.get(`/bsd/${id}/`),
  create:  (d) => api.post('/bsd/', d),
  signer:  (id,actor)=> api.post(`/bsd/${id}/signer/`, { actor }),
}
export const declarationsAPI = {
  getAll:  (p) => api.get('/declarations/', { params: p }),
  create:  (d) => api.post('/declarations/', d),
  update:  (id,d)=> api.patch(`/declarations/${id}/`, d),
  soumettre:(id)=> api.post(`/declarations/${id}/soumettre/`),
}
export const inspectionsAPI = {
  getAll:  (p) => api.get('/inspections/', { params: p }),
  create:  (d) => api.post('/inspections/', d),
}
