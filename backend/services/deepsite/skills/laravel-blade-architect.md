# Laravel + Blade + PostgreSQL — Full-Stack Architecture Guide

> Role: Senior Full-Stack Laravel Engineer  
> Principle: Deliver a **complete, working web application** — never a partial skeleton.  
> Standard: Production-ready code that passes code review on the first submission.

---

## Stack

**Laravel 11+**, Blade template engine, **Tailwind CSS** (CDN or Vite), **Alpine.js** (x-data directives), PostgreSQL 16+, Laravel Sanctum

---

## Mandatory PHP Standards

- PHP **8.2+** features: typed properties, match expressions, enums, readonly properties
- `declare(strict_types=1);` at the top of every PHP file
- **PSR-12** coding standards
- **SOLID** principles — single responsibility, dependency injection over static calls
- `camelCase` for methods, `snake_case` for variables/DB columns, `PascalCase` for classes

---

## Required composer.json Dependencies

```json
{
  "require": {
    "laravel/framework": "^11.0",
    "laravel/sanctum": "^4.0",
    "spatie/laravel-permission": "^6.0"
  },
  "require-dev": {
    "pestphp/pest": "^2.0",
    "pestphp/pest-plugin-laravel": "^2.0",
    "barryvdh/laravel-debugbar": "^3.10"
  }
}
```

---

## Mandatory File Checklist — EVERY Project MUST Include

```
routes/
  web.php                    ← Route::resource() for all entities
  api.php                    ← API routes if needed

app/Http/
  Controllers/               ← ONE controller per entity (CRUD: index/create/store/show/edit/update/destroy)
  Requests/                  ← FormRequest for store + update (never $request->validate() in controller)
  Middleware/                ← Auth guards

app/Models/                  ← Eloquent models with $fillable, relationships, casts
app/Services/                ← Business logic (thin controllers)
app/Policies/                ← ONE policy per model

resources/views/
  layouts/
    app.blade.php            ← Master layout with nav, sidebar, @yield('content')
  components/                ← Blade components (x-component)
  [entity]/
    index.blade.php          ← Paginated list table with search
    create.blade.php         ← Create form
    edit.blade.php           ← Edit form (pre-filled)
    show.blade.php           ← Detail view

database/
  migrations/                ← Timestamped, always use PostgreSQL types
  seeders/                   ← DatabaseSeeder + feature seeders with realistic data
  factories/                 ← Model factories for testing

public/
  index.php                  ← Laravel entry point

config/
  app.php                    ← App config
  database.php               ← PostgreSQL connection

.env.example                 ← All required environment variables documented
```

---

## Routes (routes/web.php)

```php
<?php
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\UserController;

Route::middleware(['auth'])->group(function () {
    Route::get('/', fn() => redirect()->route('dashboard'))->name('home');
    Route::get('/dashboard', fn() => view('dashboard'))->name('dashboard');

    Route::resource('users', UserController::class);
    Route::resource('products', ProductController::class);
    // Add Route::resource() for EVERY entity
});

Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login']);
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
```

---

## Controller Pattern (ResourceController)

```php
<?php
declare(strict_types=1);

namespace App\Http\Controllers;

use App\Http\Requests\StoreUserRequest;
use App\Http\Requests\UpdateUserRequest;
use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\View\View;

class UserController extends Controller
{
    public function index(): View
    {
        $users = User::with('roles')
            ->latest()
            ->paginate(15);

        return view('users.index', compact('users'));
    }

    public function create(): View
    {
        return view('users.create');
    }

    public function store(StoreUserRequest $request): RedirectResponse
    {
        User::create($request->validated());

        return redirect()->route('users.index')
            ->with('success', 'User created successfully.');
    }

    public function show(User $user): View
    {
        return view('users.show', compact('user'));
    }

    public function edit(User $user): View
    {
        return view('users.edit', compact('user'));
    }

    public function update(UpdateUserRequest $request, User $user): RedirectResponse
    {
        $user->update($request->validated());

        return redirect()->route('users.index')
            ->with('success', 'User updated successfully.');
    }

    public function destroy(User $user): RedirectResponse
    {
        $user->delete();

        return redirect()->route('users.index')
            ->with('success', 'User deleted successfully.');
    }
}
```

---

## FormRequest Validation

```php
<?php
declare(strict_types=1);

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreUserRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'name'     => ['required', 'string', 'max:255'],
            'email'    => ['required', 'email', 'unique:users,email'],
            'password' => ['required', 'string', 'min:8', 'confirmed'],
        ];
    }
}
```

---

## Eloquent Model

```php
<?php
declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Product extends Model
{
    use HasFactory;

    protected $fillable = [
        'name', 'description', 'price', 'stock', 'category_id', 'status',
    ];

    protected $casts = [
        'price'  => 'decimal:2',
        'stock'  => 'integer',
        'status' => 'boolean',
    ];

    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class);
    }

    public function orderItems(): HasMany
    {
        return $this->hasMany(OrderItem::class);
    }
}
```

---

## Blade Layout (resources/views/layouts/app.blade.php)

```html
<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', config('app.name'))</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    @stack('styles')
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-6">
                    <a href="{{ route('dashboard') }}" class="text-lg font-bold text-indigo-600">
                        {{ config('app.name') }}
                    </a>
                    <!-- Add nav links for each entity: Users, Products, Orders, etc. -->
                    @foreach(['users','products','orders','categories'] as $resource)
                    <a href="{{ route($resource.'.index') }}"
                       class="text-sm text-gray-600 hover:text-indigo-600 transition-colors
                              {{ request()->routeIs($resource.'.*') ? 'text-indigo-600 font-medium' : '' }}">
                        {{ ucfirst($resource) }}
                    </a>
                    @endforeach
                </div>
                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="text-sm text-gray-500 hover:text-red-500 transition-colors">
                        Logout
                    </button>
                </form>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        @if(session('success'))
            <div class="mb-4 p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
                {{ session('success') }}
            </div>
        @endif
        @if($errors->any())
            <div class="mb-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                <ul class="list-disc list-inside space-y-1">
                    @foreach($errors->all() as $error)
                        <li>{{ $error }}</li>
                    @endforeach
                </ul>
            </div>
        @endif

        @yield('content')
    </main>

    @stack('scripts')
</body>
</html>
```

---

## Blade Index View (resources/views/users/index.blade.php)

```html
@extends('layouts.app')
@section('title', 'Users')
@section('content')
<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-gray-900">Users</h1>
    <a href="{{ route('users.create') }}"
       class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + New User
    </a>
</div>

<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
            @forelse($users as $user)
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="px-6 py-4 text-sm text-gray-500">{{ $user->id }}</td>
                <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ $user->name }}</td>
                <td class="px-6 py-4 text-sm text-gray-600">{{ $user->email }}</td>
                <td class="px-6 py-4 text-sm text-gray-500">{{ $user->created_at->format('Y-m-d') }}</td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-3">
                        <a href="{{ route('users.edit', $user) }}"
                           class="text-xs text-indigo-600 hover:text-indigo-800 font-medium">Edit</a>
                        <form method="POST" action="{{ route('users.destroy', $user) }}"
                              onsubmit="return confirm('Delete this record?')">
                            @csrf @method('DELETE')
                            <button type="submit" class="text-xs text-red-500 hover:text-red-700 font-medium">
                                Delete
                            </button>
                        </form>
                    </div>
                </td>
            </tr>
            @empty
            <tr>
                <td colspan="5" class="px-6 py-12 text-center text-sm text-gray-400">No records found.</td>
            </tr>
            @endforelse
        </tbody>
    </table>
    <div class="px-6 py-4 border-t border-gray-200">
        {{ $users->links() }}
    </div>
</div>
@endsection
```

---

## Alpine.js Interactivity Pattern

```html
<!-- Dropdown menu with Alpine.js -->
<div x-data="{ open: false }" class="relative">
    <button @click="open = !open" class="...">Actions</button>
    <div x-show="open" @click.away="open = false"
         x-transition:enter="transition ease-out duration-100"
         x-transition:enter-start="opacity-0 scale-95"
         x-transition:enter-end="opacity-100 scale-100"
         class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-100 z-10">
        <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Edit</a>
        <button class="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">Delete</button>
    </div>
</div>
```

---

## PostgreSQL Migration

```php
<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('products', function (Blueprint $table) {
            $table->id();
            $table->foreignId('category_id')->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->text('description')->nullable();
            $table->decimal('price', 10, 2);
            $table->unsignedInteger('stock')->default(0);
            $table->boolean('status')->default(true);
            $table->jsonb('metadata')->nullable();   // Use jsonb, not json
            $table->timestamps();
            $table->softDeletes();

            $table->index(['category_id', 'status']);
            $table->index('created_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('products');
    }
};
```

---

## Non-Negotiables

1. **Every entity MUST have**: migration + model + controller + FormRequest (store+update) + 4 views (index/create/edit/show) + route
2. **FormRequest for ALL validation** — never `$request->validate()` in controllers
3. **Eloquent eager loading** — always `with()` to prevent N+1 queries
4. **`$fillable`** defined on every model — never use `$guarded = []`
5. **PostgreSQL only** — use `jsonb` not `json`, use `unsignedBigInteger` for FK
6. **CSRF** — `@csrf` on every form, `@method('DELETE'/'PUT')` for non-POST
7. **Pagination** — never `User::all()`, always `->paginate(15)`
8. **Tailwind CSS + Alpine.js** for styling and interactivity — no jQuery
9. **Responsive** — all views work on mobile (Tailwind `sm:`/`md:`/`lg:` breakpoints)
10. **Flash messages** — always show `session('success')` / `session('error')` in layout

---

## Anti-Patterns — NEVER Do

- Generating only migrations/models without controllers, routes, and views
- Raw SQL without parameter binding → SQL injection
- Logic in Blade views → belongs in controllers/services
- `User::all()` without pagination
- `@php` blocks in Blade for complex logic
- Storing passwords without `Hash::make()`
- Missing `@csrf` on forms
- `style=""` attributes in Blade — use Tailwind classes
- Skipping `declare(strict_types=1)` in PHP files
- Generating partial files and stopping — always complete all layers
