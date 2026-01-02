# 🎨 GitHub Entegrasyonu Frontend Bileşenleri

## 📋 Özet

Bu PR, GitHub entegrasyonu için kapsamlı frontend bileşenleri ekler. Pull Request yönetimi, Issues yönetimi, Activity feed, Branch yönetimi ve Diff viewer bileşenleri ile birlikte gerekli React hook'ları ve test dosyaları eklenmiştir.

## ✨ Yeni Özellikler

### 🔗 GitHub Webhooks
- Webhook ayarları sayfası (`github-webhook-settings.tsx`)
- Webhook event listesi (`webhook-events-list.tsx`)
- Real-time event görüntüleme

### 📝 Pull Request Yönetimi
- PR listesi (`pull-request-list.tsx`)
- PR detay sayfası (`pull-request-detail.tsx`)
- PR merge, review ve comment işlemleri
- Review ve comment görüntüleme

### 🐛 Issues Yönetimi
- Issue listesi (`issues-list.tsx`)
- Issue detay sayfası (`issue-detail.tsx`)
- Issue oluşturma formu (`issue-create-form.tsx`)
- Issue güncelleme ve kapatma
- Issue comment yönetimi

### 📊 Activity Feed
- Activity feed bileşeni (`activity-feed.tsx`)
- Activity event kartları (`activity-event-card.tsx`)
- Real-time event görüntüleme

### 🌿 Branch Yönetimi
- Branch listesi (`branches-list.tsx`)
- Branch oluşturma formu (`branch-create-form.tsx`)
- Branch karşılaştırma görünümü (`branch-compare-view.tsx`)
- Branch silme işlemi

### 🔍 Diff Viewer
- Diff viewer bileşeni (`diff-viewer.tsx`)
- Commit diff görüntüleme
- Branch/commit karşılaştırma

## 📁 Yeni Dosyalar

### Components
- `components/mgx/github-webhook-settings.tsx` - Webhook ayarları
- `components/mgx/webhook-events-list.tsx` - Webhook event listesi
- `components/mgx/pull-request-list.tsx` - PR listesi
- `components/mgx/pull-request-detail.tsx` - PR detay sayfası
- `components/mgx/issues-list.tsx` - Issue listesi
- `components/mgx/issue-detail.tsx` - Issue detay sayfası
- `components/mgx/issue-create-form.tsx` - Issue oluşturma formu
- `components/mgx/activity-feed.tsx` - Activity feed
- `components/mgx/activity-event-card.tsx` - Activity event kartı
- `components/mgx/branches-list.tsx` - Branch listesi
- `components/mgx/branch-create-form.tsx` - Branch oluşturma formu
- `components/mgx/branch-compare-view.tsx` - Branch karşılaştırma
- `components/mgx/diff-viewer.tsx` - Diff viewer

### Hooks
- `hooks/useWebhookEvents.ts` - Webhook event hook'u
- `hooks/usePullRequests.ts` - Pull Request hook'u
- `hooks/useIssues.ts` - Issues hook'u
- `hooks/useActivityFeed.ts` - Activity feed hook'u
- `hooks/useBranches.ts` - Branches hook'u
- `hooks/useDiffs.ts` - Diffs hook'u (implicit)

### Pages
- `app/mgx/repositories/[repoId]/pull-requests/page.tsx` - PR listesi sayfası
- `app/mgx/repositories/[repoId]/pull-requests/[prNumber]/page.tsx` - PR detay sayfası
- `app/mgx/repositories/[repoId]/issues/page.tsx` - Issue listesi sayfası
- `app/mgx/repositories/[repoId]/issues/[issueNumber]/page.tsx` - Issue detay sayfası
- `app/mgx/repositories/[repoId]/activity/page.tsx` - Activity feed sayfası
- `app/mgx/repositories/[repoId]/branches/page.tsx` - Branch listesi sayfası
- `app/mgx/repositories/[repoId]/branches/[branchName]/page.tsx` - Branch detay sayfası
- `app/mgx/repositories/[repoId]/diffs/[commitSha]/page.tsx` - Commit diff sayfası
- `app/mgx/repositories/[repoId]/diffs/compare/page.tsx` - Compare diff sayfası

### Tests
- `__tests__/mgx/pull-request-list.test.tsx` - PR listesi testleri
- `__tests__/mgx/issues-list.test.tsx` - Issue listesi testleri
- `__tests__/mgx/activity-feed.test.tsx` - Activity feed testleri

## 🔄 Güncellenen Dosyalar

### API & Types
- `lib/api.ts` - GitHub API fonksiyonları eklendi:
  - `getWebhookEvents()`
  - `listPullRequests()`, `getPullRequest()`, `mergePullRequest()`
  - `createPullRequestReview()`, `createPullRequestComment()`
  - `listPullRequestReviews()`, `listPullRequestComments()`
  - `listIssues()`, `getIssue()`, `createIssue()`, `updateIssue()`, `closeIssue()`
  - `createIssueComment()`, `listIssueComments()`
  - `getActivityFeed()`, `getCommitHistory()`
  - `listBranches()`, `createBranch()`, `deleteBranch()`, `compareBranches()`
  - `getCommitDiff()`, `getCompareDiff()`

- `lib/types.ts` - GitHub type tanımları eklendi:
  - `WebhookEvent`, `PullRequest`, `PRReview`, `PRComment`
  - `Issue`, `IssueComment`
  - `ActivityEvent`, `Branch`, `BranchCompare`
  - `DiffFile`, `DiffStatistics`, `DiffResponse`

- `lib/utils.ts` - Utility fonksiyonları güncellendi

### Settings
- `app/mgx/settings/git/page.tsx` - GitHub webhook ayarları eklendi

### Config
- `next.config.ts` - Gerekli config güncellemeleri

## 🗑️ Silinen Dosyalar

- `.dockerignore` - Ana repo'da yönetilecek
- `Dockerfile` - Ana repo'da yönetilecek

## 🎨 UI/UX Özellikleri

### Pull Request Yönetimi
- ✅ PR listesi (open/closed filtreleme)
- ✅ PR detay görüntüleme (title, body, author, state)
- ✅ PR merge butonu
- ✅ Review oluşturma (APPROVE, REQUEST_CHANGES, COMMENT)
- ✅ Comment ekleme
- ✅ Review ve comment listesi

### Issues Yönetimi
- ✅ Issue listesi (open/closed/all filtreleme)
- ✅ Issue detay görüntüleme
- ✅ Issue oluşturma formu
- ✅ Issue güncelleme
- ✅ Issue kapatma
- ✅ Comment ekleme ve görüntüleme
- ✅ Labels ve assignees görüntüleme

### Activity Feed
- ✅ Real-time activity feed
- ✅ Event kartları (push, pull_request, issues, vb.)
- ✅ Event metadata görüntüleme
- ✅ Time ago formatı

### Branch Yönetimi
- ✅ Branch listesi
- ✅ Branch oluşturma formu
- ✅ Branch silme
- ✅ Branch karşılaştırma görünümü

### Diff Viewer
- ✅ Commit diff görüntüleme
- ✅ Branch/commit karşılaştırma
- ✅ File-level diff detayları
- ✅ Syntax highlighting

## 🧪 Testler

### Yeni Testler
- ✅ `pull-request-list.test.tsx` - PR listesi component testleri
- ✅ `issues-list.test.tsx` - Issue listesi component testleri
- ✅ `activity-feed.test.tsx` - Activity feed component testleri

### Test Kapsamı
- Component rendering testleri
- Loading state testleri
- Error state testleri
- User interaction testleri

## 🔧 Teknik Detaylar

### React Hooks

#### useWebhookEvents
```typescript
const { events, isLoading, error, refetch } = useWebhookEvents(linkId, options);
```

#### usePullRequests
```typescript
const { prs, isLoading, error, refetch } = usePullRequests(linkId, state, options);
```

#### useIssues
```typescript
const { issues, isLoading, error, refetch } = useIssues(linkId, state, options);
```

#### useActivityFeed
```typescript
const { events, isLoading, error, refetch } = useActivityFeed(linkId, options);
```

#### useBranches
```typescript
const { branches, isLoading, error, refetch } = useBranches(linkId, options);
```

### API Integration
- SWR kullanılarak data fetching
- Automatic revalidation
- Error handling
- Loading states

## 📱 Responsive Design
- ✅ Mobile-friendly layout
- ✅ Tablet ve desktop uyumlu
- ✅ Touch-friendly interactions

## ♿ Accessibility
- ✅ Semantic HTML
- ✅ ARIA labels
- ✅ Keyboard navigation
- ✅ Screen reader uyumlu

## 🎯 Kullanıcı Deneyimi

### Özellikler
- ✅ Real-time updates (SWR)
- ✅ Loading states
- ✅ Error handling ve mesajları
- ✅ Toast notifications (sonner)
- ✅ Confirmation dialogs
- ✅ Form validation

## ✅ Checklist

- [x] GitHub webhook ayarları UI
- [x] PR yönetimi bileşenleri
- [x] Issues yönetimi bileşenleri
- [x] Activity feed bileşeni
- [x] Branch yönetimi bileşenleri
- [x] Diff viewer bileşeni
- [x] React hook'ları
- [x] API entegrasyonu
- [x] Type definitions
- [x] Test dosyaları
- [x] Responsive design
- [x] Error handling
- [x] Loading states

## 📊 İstatistikler

- **34 dosya değişti**
- **3,612 satır eklendi**
- **136 satır silindi**
- **13 yeni component**
- **6 yeni React hook**
- **9 yeni sayfa**
- **3 yeni test dosyası**

## 🔗 İlgili PR'lar

- Backend PR: [mgx-ai PR](#) (GitHub entegrasyonu backend servisleri)

## 🚀 Deployment

### Gereksinimler
- Backend API endpoints aktif olmalı
- GitHub token yapılandırılmış olmalı
- Webhook secret ayarlanmış olmalı

### Test
```bash
npm test
# veya
yarn test
```

## 🎉 Sonuç

Bu PR, GitHub entegrasyonu için kapsamlı frontend bileşenleri ekler. Kullanıcılar artık GitHub webhooks, PR'lar, Issues, Activity feed, Branches ve Diffs'i frontend üzerinden yönetebilir.

