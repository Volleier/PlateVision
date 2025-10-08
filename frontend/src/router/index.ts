import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Check from '../views/Check.vue'
import Upload from '../views/Upload.vue'

const routes = [
  { path: '/', name: 'Home', component: Home, meta: { hideHeader: true } },
  { path: '/check', name: 'Check', component: Check },
  { path: '/upload', name: 'Upload', component: Upload }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
