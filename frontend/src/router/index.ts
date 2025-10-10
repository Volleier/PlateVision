import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import UploadImage from '../views/UploadImage.vue'
import UploadVideo from '../views/UploadVideo.vue'

const routes = [
  { path: '/',              name: 'home',       component: Home,        meta: { hideHeader: true } },
  { path: '/upload-image',  name: 'uploadImage',component: UploadImage },
  { path: '/upload-video',  name: 'uploadVideo',component: UploadVideo },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
