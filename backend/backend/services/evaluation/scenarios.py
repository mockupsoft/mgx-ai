# -*- coding: utf-8 -*-
"""backend.services.evaluation.scenarios

Test scenarios library for AI evaluation framework.
Contains baseline test cases categorized by complexity and domain.
"""

import json
from typing import Dict, List, Any
from ..db.models.entities_evaluation import EvaluationScenario
from ..db.models.enums import ComplexityLevel


class ScenarioLibrary:
    """Library of evaluation scenarios for testing agent performance."""
    
    def __init__(self):
        self.scenarios = self._initialize_scenarios()
    
    def _initialize_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Initialize the scenario library with baseline test cases."""
        
        return {
            # ==================== EASY LEVEL SCENARIOS ====================
            
            "create_simple_endpoint": {
                "name": "Create Simple FastAPI Endpoint",
                "description": "Create a basic FastAPI endpoint with proper HTTP methods and error handling",
                "category": "api_development",
                "complexity_level": ComplexityLevel.EASY,
                "language": "Python",
                "framework": "FastAPI",
                "prompt": """Create a FastAPI endpoint for user authentication.

Requirements:
- Accept POST requests to /auth/login
- Accept JSON body with 'username' and 'password' fields
- Return appropriate HTTP status codes
- Include basic error handling
- Add docstring and type hints

Return only the code without explanations.""",
                "expected_output": """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user_id: int

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    '''
    Authenticate user and return access token.
    
    Args:
        request: Login credentials
        
    Returns:
        Access token and user information
        
    Raises:
        HTTPException: For invalid credentials
    '''
    # Basic validation
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # Simulate authentication logic
    if request.username == "admin" and request.password == "secret":
        return LoginResponse(
            token="mock_jwt_token",
            user_id=1
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")""",
                "evaluation_criteria": {
                    "code_safety": {
                        "weight": 0.20,
                        "requirements": [
                            "Input validation",
                            "Error handling",
                            "No hardcoded secrets in production code",
                            "Proper HTTP status codes"
                        ]
                    },
                    "code_quality": {
                        "weight": 0.15,
                        "requirements": [
                            "Proper class structure",
                            "Type hints",
                            "Clear variable names",
                            "Consistent formatting"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "Correct FastAPI syntax",
                            "Proper request/response models",
                            "Working endpoint structure"
                        ]
                    }
                },
                "estimated_duration_minutes": 10,
                "tags": ["fastapi", "authentication", "basic", "beginner"]
            },
            
            "simple_component": {
                "name": "Create Simple React Component",
                "description": "Create a basic React functional component with state management",
                "category": "frontend_ui",
                "complexity_level": ComplexityLevel.EASY,
                "language": "JavaScript",
                "framework": "React",
                "prompt": """Create a React functional component for a counter.

Requirements:
- Functional component using hooks
- State management for counter value
- Increment/decrement buttons
- Display current count
- PropTypes for component props
- Basic styling

Return only the component code without explanations.""",
                "expected_output": """import React, { useState } from 'react';
import PropTypes from 'prop-types';

const Counter = ({ initialValue = 0 }) => {
  const [count, setCount] = useState(initialValue);

  const increment = () => {
    setCount(prevCount => prevCount + 1);
  };

  const decrement = () => {
    setCount(prevCount => prevCount - 1);
  };

  return (
    <div className="counter-component">
      <h2>Counter: {count}</h2>
      <div className="button-group">
        <button onClick={decrement} className="btn btn-decrement">
          -
        </button>
        <button onClick={increment} className="btn btn-increment">
          +
        </button>
      </div>
    </div>
  );
};

Counter.propTypes = {
  initialValue: PropTypes.number
};

Counter.defaultProps = {
  initialValue: 0
};

export default Counter;""",
                "evaluation_criteria": {
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Proper React functional component structure",
                            "Correct useState usage",
                            "PropTypes validation",
                            "Default props"
                        ]
                    },
                    "readability": {
                        "weight": 0.15,
                        "requirements": [
                            "Clear component name",
                            "Descriptive variable names",
                            "Clean JSX structure",
                            "Proper formatting"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "State updates correctly",
                            "Event handlers work",
                            "Component renders properly"
                        ]
                    }
                },
                "estimated_duration_minutes": 8,
                "tags": ["react", "hooks", "state", "basic", "functional-component"]
            },
            
            "database_model": {
                "name": "Create SQLAlchemy Model",
                "description": "Create a basic SQLAlchemy model with relationships",
                "category": "backend_development",
                "complexity_level": ComplexityLevel.EASY,
                "language": "Python",
                "framework": "SQLAlchemy",
                "prompt": """Create a SQLAlchemy model for a blog post.

Requirements:
- SQLAlchemy declarative model
- Primary key and required fields
- String fields with length limits
- DateTime field for timestamps
- Text field for content
- __repr__ method
- Proper imports

Return only the model code without explanations.""",
                "expected_output": """from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class BlogPost:
    __tablename__ = 'blog_posts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published = Column(Integer, default=0, nullable=False)  # 0 = draft, 1 = published
    
    # Relationships
    author = relationship("User", back_populates="blog_posts")
    
    def __repr__(self):
        return f'<BlogPost(id={self.id}, title="{self.title[:20]}...")>'""",
                "evaluation_criteria": {
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Correct SQLAlchemy syntax",
                            "Proper model structure",
                            "Relationship definitions",
                            "Type hints"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.15,
                        "requirements": [
                            "Appropriate field constraints",
                            "Indexes on frequently queried fields",
                            "Timestamps for audit trail",
                            "Clear __repr__ method"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "Model can be instantiated",
                            "Fields are accessible",
                            "Relationships work correctly"
                        ]
                    }
                },
                "estimated_duration_minutes": 12,
                "tags": ["sqlalchemy", "model", "database", "relationships", "basic"]
            },
            
            # ==================== MEDIUM LEVEL SCENARIOS ====================
            
            "restful_api": {
                "name": "Create Complete RESTful API",
                "description": "Create a complete REST API with CRUD operations, validation, and error handling",
                "category": "api_development",
                "complexity_level": ComplexityLevel.MEDIUM,
                "language": "Python",
                "framework": "FastAPI",
                "prompt": """Create a complete RESTful API for managing tasks.

Requirements:
- FastAPI application with proper structure
- Pydantic models for request/response validation
- CRUD operations (Create, Read, Update, Delete)
- Proper HTTP status codes
- Error handling and validation
- Database integration (simulated)
- Pagination support
- OpenAPI documentation
- Authentication middleware

Return the complete API code without explanations.""",
                "expected_output": """from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

app = FastAPI(title="Task Management API", version="1.0.0")
security = HTTPBearer()

# Pydantic Models
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: int = Field(1, ge=1, le=5, description="Task priority (1-5)")
    status: str = Field("pending", description="Task status")

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None

class TaskResponse(TaskBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Simulated database (in production, use actual database)
tasks_db: Dict[str, Dict[str, Any]] = {}

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Simulate authentication logic
    return {"user_id": "user123", "username": "testuser"}

# Helper functions
async def get_task_or_404(task_id: str) -> Dict[str, Any]:
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# API Endpoints
@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(get_current_user)
):
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        **task_data.dict(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "created_by": current_user["user_id"]
    }
    tasks_db[task_id] = task
    return task

@app.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    filtered_tasks = list(tasks_db.values())
    
    if status:
        filtered_tasks = [t for t in filtered_tasks if t["status"] == status]
    
    # Apply pagination
    return filtered_tasks[skip:skip + limit]

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    return await get_task_or_404(task_id)

@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_user: dict = Depends(get_current_user)
):
    task = await get_task_or_404(task_id)
    
    update_data = task_data.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    task.update(update_data)
    tasks_db[task_id] = task
    
    return task

@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del tasks_db[task_id]

@app.get("/tasks/{task_id}/progress")
async def get_task_progress(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    task = await get_task_or_404(task_id)
    
    # Calculate progress based on status
    status_progress = {
        "pending": 0,
        "in_progress": 50,
        "completed": 100,
        "cancelled": 0
    }
    
    return {
        "task_id": task_id,
        "progress_percentage": status_progress.get(task["status"], 0),
        "status": task["status"]
    }""",
                "evaluation_criteria": {
                    "code_safety": {
                        "weight": 0.20,
                        "requirements": [
                            "Input validation with Pydantic",
                            "Authentication middleware",
                            "Error handling for edge cases",
                            "SQL injection prevention"
                        ]
                    },
                    "code_quality": {
                        "weight": 0.15,
                        "requirements": [
                            "Clean API structure",
                            "Proper separation of concerns",
                            "Consistent naming conventions",
                            "Type hints throughout"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.15,
                        "requirements": [
                            "RESTful HTTP methods and status codes",
                            "Proper error responses",
                            "Pagination implementation",
                            "OpenAPI documentation"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "Complete CRUD operations",
                            "Proper request/response handling",
                            "Database operations work correctly",
                            "All endpoints are functional"
                        ]
                    },
                    "maintainability": {
                        "weight": 0.15,
                        "requirements": [
                            "Modular code structure",
                            "Reusable components",
                            "Clear documentation",
                            "Easy to extend"
                        ]
                    }
                },
                "estimated_duration_minutes": 45,
                "tags": ["fastapi", "rest", "crud", "authentication", "pagination", "intermediate"]
            },
            
            "react_app": {
                "name": "Create React Application with State Management",
                "description": "Create a React application with multiple components, state management, and routing",
                "category": "frontend_ui",
                "complexity_level": ComplexityLevel.MEDIUM,
                "language": "JavaScript",
                "framework": "React",
                "prompt": """Create a React todo application with comprehensive features.

Requirements:
- Multiple components (TodoList, TodoItem, AddTodo)
- Context API for state management
- Local storage persistence
- Filtering (all, active, completed)
- Input validation
- Error handling
- Responsive design
- PropTypes validation

Return the complete application code without explanations.""",
                "expected_output": """import React, { useState, useEffect, useContext, createContext } from 'react';
import PropTypes from 'prop-types';

// Context for state management
const TodoContext = createContext();

const TodoProvider = ({ children }) => {
  const [todos, setTodos] = useState([]);
  const [filter, setFilter] = useState('all');

  // Load from localStorage
  useEffect(() => {
    const savedTodos = localStorage.getItem('todos');
    if (savedTodos) {
      setTodos(JSON.parse(savedTodos));
    }
  }, []);

  // Save to localStorage
  useEffect(() => {
    localStorage.setItem('todos', JSON.stringify(todos));
  }, [todos]);

  const addTodo = (text) => {
    if (text.trim()) {
      const newTodo = {
        id: Date.now(),
        text: text.trim(),
        completed: false,
        createdAt: new Date().toISOString()
      };
      setTodos(prev => [...prev, newTodo]);
    }
  };

  const toggleTodo = (id) => {
    setTodos(prev => prev.map(todo => 
      todo.id === id ? { ...todo, completed: !todo.completed } : todo
    ));
  };

  const deleteTodo = (id) => {
    setTodos(prev => prev.filter(todo => todo.id !== id));
  };

  const filteredTodos = todos.filter(todo => {
    if (filter === 'active') return !todo.completed;
    if (filter === 'completed') return todo.completed;
    return true;
  });

  const value = {
    todos: filteredTodos,
    filter,
    setFilter,
    addTodo,
    toggleTodo,
    deleteTodo,
    stats: {
      total: todos.length,
      active: todos.filter(t => !t.completed).length,
      completed: todos.filter(t => t.completed).length
    }
  };

  return (
    <TodoContext.Provider value={value}>
      {children}
    </TodoContext.Provider>
  );
};

// AddTodo Component
const AddTodo = () => {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const { addTodo } = useContext(TodoContext);

  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!text.trim()) {
      setError('Please enter a todo item');
      return;
    }
    
    if (text.length > 100) {
      setError('Todo item is too long (max 100 characters)');
      return;
    }

    addTodo(text);
    setText('');
    setError('');
  };

  return (
    <form onSubmit={handleSubmit} className="add-todo">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="What needs to be done?"
        className="todo-input"
        maxLength={100}
      />
      <button type="submit" className="add-btn">Add</button>
      {error && <span className="error">{error}</span>}
    </form>
  );
};

// TodoItem Component
const TodoItem = ({ todo }) => {
  const { toggleTodo, deleteTodo } = useContext(TodoContext);

  return (
    <div className={`todo-item ${todo.completed ? 'completed' : ''}`}>
      <input
        type="checkbox"
        checked={todo.completed}
        onChange={() => toggleTodo(todo.id)}
        className="todo-checkbox"
      />
      <span className="todo-text">{todo.text}</span>
      <button 
        onClick={() => deleteTodo(todo.id)}
        className="delete-btn"
        aria-label="Delete todo"
      >
        ×
      </button>
    </div>
  );
};

TodoItem.propTypes = {
  todo: PropTypes.shape({
    id: PropTypes.number.isRequired,
    text: PropTypes.string.isRequired,
    completed: PropTypes.bool.isRequired
  }).isRequired
};

// TodoList Component
const TodoList = () => {
  const { todos } = useContext(TodoContext);

  if (todos.length === 0) {
    return <p className="empty-state">No todos found</p>;
  }

  return (
    <div className="todo-list">
      {todos.map(todo => (
        <TodoItem key={todo.id} todo={todo} />
      ))}
    </div>
  );
};

// FilterButtons Component
const FilterButtons = () => {
  const { filter, setFilter } = useContext(TodoContext);
  const filters = ['all', 'active', 'completed'];

  return (
    <div className="filter-buttons">
      {filters.map(f => (
        <button
          key={f}
          onClick={() => setFilter(f)}
          className={`filter-btn ${filter === f ? 'active' : ''}`}
        >
          {f.charAt(0).toUpperCase() + f.slice(1)}
        </button>
      ))}
    </div>
  );
};

// Stats Component
const Stats = () => {
  const { stats } = useContext(TodoContext);

  return (
    <div className="stats">
      <span>Total: {stats.total}</span>
      <span>Active: {stats.active}</span>
      <span>Completed: {stats.completed}</span>
    </div>
  );
};

// Main TodoApp Component
const TodoApp = () => {
  return (
    <TodoProvider>
      <div className="todo-app">
        <h1>Todo App</h1>
        <AddTodo />
        <FilterButtons />
        <TodoList />
        <Stats />
      </div>
    </TodoProvider>
  );
};

export default TodoApp;""",
                "evaluation_criteria": {
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Proper component composition",
                            "State management with Context API",
                            "Clean component structure",
                            "PropTypes validation"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.15,
                        "requirements": [
                            "Separation of concerns",
                            "Reusable components",
                            "Proper event handling",
                            "Input validation and error handling"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "All CRUD operations work",
                            "Filtering functionality",
                            "Local storage persistence",
                            "State management works correctly"
                        ]
                    },
                    "readability": {
                        "weight": 0.15,
                        "requirements": [
                            "Clear component names",
                            "Descriptive variable names",
                            "Well-structured JSX",
                            "Logical code organization"
                        ]
                    },
                    "maintainability": {
                        "weight": 0.15,
                        "requirements": [
                            "Modular component design",
                            "Easy to extend",
                            "Clear separation of concerns",
                            "Consistent coding style"
                        ]
                    }
                },
                "estimated_duration_minutes": 60,
                "tags": ["react", "context-api", "state-management", "local-storage", "components", "intermediate"]
            },
            
            "complex_query": {
                "name": "Create Complex Database Query",
                "description": "Create a complex SQLAlchemy query with joins, aggregations, and subqueries",
                "category": "backend_development",
                "complexity_level": ComplexityLevel.MEDIUM,
                "language": "Python",
                "framework": "SQLAlchemy",
                "prompt": """Create a complex SQLAlchemy query for an analytics dashboard.

Requirements:
- Join multiple tables
- Aggregate functions (COUNT, SUM, AVG)
- GROUP BY and HAVING clauses
- Subqueries
- Filtering and ordering
- Proper SQLAlchemy syntax
- Performance optimization

Return the complete query code without explanations.""",
                "expected_output": """from sqlalchemy import (
    select, func, desc, asc, and_, or_, case
)
from sqlalchemy.orm import aliased

def get_user_analytics(session):
    """
    Get comprehensive user analytics with complex joins and aggregations.
    
    Returns:
        List of dictionaries with user analytics data
    """
    
    # Define table aliases for readability
    User = aliased(UserModel)
    Order = aliased(OrderModel)
    Product = aliased(ProductModel)
    Review = aliased(ReviewModel)
    
    # Main query with multiple joins and aggregations
    query = select(
        # User information
        User.id.label('user_id'),
        User.username,
        User.email,
        User.created_at.label('user_created_at'),
        
        # Order analytics
        func.count(Order.id).label('total_orders'),
        func.coalesce(func.sum(Order.total_amount), 0).label('total_spent'),
        func.coalesce(func.avg(Order.total_amount), 0).label('avg_order_value'),
        func.max(Order.created_at).label('last_order_date'),
        
        # Order status breakdown
        func.sum(case([(Order.status == 'completed', 1)], else_=0)).label('completed_orders'),
        func.sum(case([(Order.status == 'pending', 1)], else_=0)).label('pending_orders'),
        func.sum(case([(Order.status == 'cancelled', 1)], else_=0)).label('cancelled_orders'),
        
        # Review analytics
        func.count(Review.id).label('total_reviews'),
        func.coalesce(func.avg(Review.rating), 0).label('avg_rating'),
        func.sum(case([(Review.rating >= 4, 1)], else_=0)).label('positive_reviews'),
        
        # Derived metrics
        func.extract('day', func.now() - User.created_at).label('days_since_registration'),
        func.extract('day', func.now() - func.max(Order.created_at)).label('days_since_last_order')
        
    ).select_from(
        # Base table with left joins to include users without orders
        User.outerjoin(Order, User.id == Order.user_id)
        .outerjoin(Product, Order.product_id == Product.id)
        .outerjoin(Review, User.id == Review.user_id)
    ).group_by(
        User.id, User.username, User.email, User.created_at
    ).having(
        # Filter users with at least 1 order or review
        or_(
            func.count(Order.id) > 0,
            func.count(Review.id) > 0
        )
    ).order_by(
        # Order by total spent descending, then by username
        desc(func.coalesce(func.sum(Order.total_amount), 0)),
        asc(User.username)
    )
    
    # Add filtering parameters if needed
    if filter_active_users_only:
        query = query.having(
            func.count(Order.id) >= 1
        )
    
    # Add pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    results = session.execute(query).fetchall()
    
    # Process results into dictionaries
    analytics = []
    for row in results:
        analytics.append({
            'user_id': row.user_id,
            'username': row.username,
            'email': row.email,
            'user_created_at': row.user_created_at,
            'total_orders': row.total_orders,
            'total_spent': float(row.total_spent or 0),
            'avg_order_value': float(row.avg_order_value or 0),
            'last_order_date': row.last_order_date,
            'completed_orders': row.completed_orders,
            'pending_orders': row.pending_orders,
            'cancelled_orders': row.cancelled_orders,
            'total_reviews': row.total_reviews,
            'avg_rating': float(row.avg_rating or 0),
            'positive_reviews': row.positive_reviews,
            'days_since_registration': row.days_since_registration,
            'days_since_last_order': row.days_since_last_order,
            # Derived insights
            'customer_lifetime_value': float(row.total_spent or 0),
            'engagement_score': calculate_engagement_score(row),
            'customer_segment': classify_customer(row)
        })
    
    return analytics

def calculate_engagement_score(row):
    """Calculate a customer engagement score based on multiple factors."""
    orders_score = min(row.total_orders * 2, 20)  # Max 20 points for orders
    review_score = min(row.total_reviews * 3, 15)  # Max 15 points for reviews
    recency_score = max(0, 10 - (row.days_since_last_order or 999) / 30)  # Max 10 points for recency
    
    return round(orders_score + review_score + recency_score, 2)

def classify_customer(row):
    """Classify customer into segments based on analytics."""
    if row.total_spent >= 1000 and row.total_orders >= 10:
        return 'VIP'
    elif row.total_spent >= 500 and row.total_orders >= 5:
        return 'Loyal'
    elif row.total_orders >= 3:
        return 'Regular'
    elif row.total_orders >= 1:
        return 'New'
    else:
        return 'Prospect'

# Additional complex query for product performance
def get_product_performance_analytics(session):
    """Get product performance analytics with time-based aggregations."""
    
    # Subquery for monthly sales
    monthly_sales = select(
        Product.id.label('product_id'),
        func.date_trunc('month', Order.created_at).label('month'),
        func.count(Order.id).label('monthly_orders'),
        func.sum(Order.total_amount).label('monthly_revenue')
    ).select_from(
        Product.join(Order, Product.id == Order.product_id)
    ).group_by(
        Product.id, func.date_trunc('month', Order.created_at)
    ).subquery()
    
    # Main query using the subquery
    query = select(
        Product.id,
        Product.name,
        Product.category,
        Product.price,
        func.count(Order.id).label('total_orders'),
        func.sum(Order.total_amount).label('total_revenue'),
        func.avg(Review.rating).label('avg_rating'),
        func.count(Review.id).label('total_reviews'),
        # Monthly trends
        func.avg(monthly_sales.c.monthly_orders).label('avg_monthly_orders'),
        func.avg(monthly_sales.c.monthly_revenue).label('avg_monthly_revenue'),
        # Performance indicators
        case([
            (func.sum(Order.total_amount) >= 10000, 'High Performer'),
            (func.sum(Order.total_amount) >= 5000, 'Good Performer'),
            (func.sum(Order.total_amount) >= 1000, 'Average Performer')
        ], else_='Low Performer').label('performance_tier')
    ).select_from(
        Product.outerjoin(Order, Product.id == Order.product_id)
        .outerjoin(Review, Product.id == Review.product_id)
        .join(monthly_sales, Product.id == monthly_sales.c.product_id)
    ).group_by(
        Product.id, Product.name, Product.category, Product.price
    ).having(
        func.sum(Order.total_amount) > 0  # Only products with sales
    ).order_by(
        desc(func.sum(Order.total_amount))
    )
    
    return session.execute(query).fetchall()""",
                "evaluation_criteria": {
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Proper SQLAlchemy query syntax",
                            "Correct use of joins and aliases",
                            "Clear variable naming",
                            "Well-structured functions"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.15,
                        "requirements": [
                            "Efficient query structure",
                            "Proper aggregation functions",
                            "Subquery usage where appropriate",
                            "Performance considerations"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "Complex joins work correctly",
                            "Aggregations produce accurate results",
                            "Filtering and ordering work",
                            "Business logic is sound"
                        ]
                    },
                    "maintainability": {
                        "weight": 0.20,
                        "requirements": [
                            "Modular query functions",
                            "Reusable query patterns",
                            "Clear documentation",
                            "Easy to modify and extend"
                        ]
                    },
                    "performance": {
                        "weight": 0.20,
                        "requirements": [
                            "Optimized query structure",
                            "Appropriate indexing hints",
                            "Efficient grouping and filtering",
                            "Minimal unnecessary operations"
                        ]
                    }
                },
                "estimated_duration_minutes": 75,
                "tags": ["sqlalchemy", "complex-query", "analytics", "joins", "aggregations", "subqueries", "intermediate"]
            },
            
            # ==================== HARD LEVEL SCENARIOS ====================
            
            "microservice": {
                "name": "Create Microservice with Multiple Components",
                "description": "Create a complete microservice with authentication, database, caching, and API gateway",
                "category": "backend_development",
                "complexity_level": ComplexityLevel.HARD,
                "language": "Python",
                "framework": "FastAPI",
                "prompt": """Create a comprehensive user management microservice.

Requirements:
- FastAPI application with proper structure
- JWT authentication with refresh tokens
- SQLAlchemy models with relationships
- Redis caching layer
- Background tasks with Celery
- API rate limiting
- Request validation and sanitization
- Comprehensive error handling
- Health checks and monitoring
- Docker configuration
- Database migrations
- API documentation
- Testing setup

Return the complete microservice code without explanations.""",
                "expected_output": """# main.py - FastAPI application entry point
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import redis
import logging
from typing import Optional

# Import modules
from .database import get_db, init_db
from .models import User, UserProfile
from .schemas import UserCreate, UserResponse, TokenResponse
from .auth import authenticate_user, create_access_token, verify_token
from .cache import get_cache_client, cache_user_profile
from .tasks import send_welcome_email
from .middleware import RateLimitMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting User Management Service")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down User Management Service")

# Initialize FastAPI app
app = FastAPI(
    title="User Management Service",
    description="Comprehensive user management microservice",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(RateLimitMiddleware, calls=100, period=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "*.company.com"]
)

# Security
security = HTTPBearer()

# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check cache first
    cache_key = f"user:{payload.get('sub')}"
    cached_user = redis_client.get(cache_key)
    
    if cached_user:
        return User.parse_raw(cached_user)
    
    # Query database
    user = db.query(User).filter(User.id == payload.get('sub')).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cache user data
    redis_client.setex(cache_key, 3600, user.json())  # 1 hour expiry
    
    return user

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Check database connection
        db = next(get_db())
        db.execute("SELECT 1")
        
        # Check Redis connection
        redis_client.ping()
        
        return {"status": "healthy", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(User).filter(
        or_(User.email == user_data.email, User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    hashed_password = pwd_context.hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create user profile
    profile = UserProfile(
        user_id=user.id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        created_at=datetime.utcnow()
    )
    
    db.add(profile)
    db.commit()
    
    # Cache user data
    await cache_user_profile(user, profile)
    
    # Background task - send welcome email
    background_tasks.add_task(send_welcome_email.delay, user.id)
    
    logger.info(f"User registered: {user.id}")
    return UserResponse.from_orm(user)

@app.post("/auth/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db=Depends(get_db)
):
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Log login
    logger.info(f"User logged in: {user.id}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800  # 30 minutes
    )

# User management endpoints
@app.get("/users/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return UserResponse.from_orm(current_user)

@app.put("/users/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Update user fields
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    # Update cache
    await cache_user_profile(current_user, None)
    
    logger.info(f"User updated: {current_user.id}")
    return UserResponse.from_orm(current_user)

@app.delete("/users/me")
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Soft delete
    current_user.is_active = False
    current_user.deleted_at = datetime.utcnow()
    db.commit()
    
    # Remove from cache
    cache_key = f"user:{current_user.id}"
    redis_client.delete(cache_key)
    
    logger.info(f"User deleted: {current_user.id}")
    return {"message": "User deleted successfully"}

# Admin endpoints
@app.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(User).filter(User.is_active == True)
    
    if search:
        query = query.filter(
            or_(
                User.username.contains(search),
                User.email.contains(search)
            )
        )
    
    users = query.offset(skip).limit(limit).all()
    return [UserResponse.from_orm(user) for user in users]

@app.put("/admin/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    user.activated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"User activated by admin: {user_id}")
    return {"message": "User activated successfully"}

# Background task endpoints
@app.post("/admin/users/{user_id}/send-verification")
async def send_verification_email(
    user_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Check admin permissions
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    background_tasks.add_task(send_verification_email.delay, user_id)
    return {"message": "Verification email queued"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)""",
                "evaluation_criteria": {
                    "code_safety": {
                        "weight": 0.25,
                        "requirements": [
                            "Input validation and sanitization",
                            "Authentication and authorization",
                            "SQL injection prevention",
                            "Rate limiting implementation",
                            "Secure password handling"
                        ]
                    },
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Clean architecture and separation of concerns",
                            "Proper async/await usage",
                            "Error handling and logging",
                            "Code organization and modularity"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.20,
                        "requirements": [
                            "Microservice design patterns",
                            "Caching strategy implementation",
                            "Background task handling",
                            "Health check implementation",
                            "API documentation standards"
                        ]
                    },
                    "functionality": {
                        "weight": 0.20,
                        "requirements": [
                            "Complete user management features",
                            "Authentication flow works correctly",
                            "Database operations are functional",
                            "All endpoints respond appropriately"
                        ]
                    },
                    "performance": {
                        "weight": 0.15,
                        "requirements": [
                            "Efficient database queries",
                            "Proper caching implementation",
                            "Async operation optimization",
                            "Resource usage considerations"
                        ]
                    }
                },
                "estimated_duration_minutes": 180,
                "tags": ["microservice", "fastapi", "authentication", "redis", "celery", "rate-limiting", "advanced"]
            },
            
            "fullstack_app": {
                "name": "Create Full-Stack Web Application",
                "description": "Create a complete full-stack application with React frontend and FastAPI backend",
                "category": "fullstack_development",
                "complexity_level": ComplexityLevel.HARD,
                "language": "Python/JavaScript",
                "framework": "FastAPI/React",
                "prompt": """Create a complete e-commerce application with React frontend and FastAPI backend.

Requirements:
- React frontend with routing and state management
- FastAPI backend with authentication
- Database models for products, orders, users
- Shopping cart functionality
- Payment integration (mock)
- Order management system
- Real-time updates using WebSockets
- Responsive design
- Error boundaries and loading states
- Testing setup
- Docker configuration

Return the complete application code without explanations.""",
                "expected_output": """# This would be a very large file - showing structure
# Frontend: React components with routing, state management, WebSocket integration
# Backend: FastAPI with models, authentication, WebSocket endpoints, payment processing
# Shared: Types, validation schemas, API contracts

# Frontend Structure (React)
# - src/
#   - components/
#     - ProductList.jsx
#     - ProductCard.jsx
#     - ShoppingCart.jsx
#     - Checkout.jsx
#     - UserProfile.jsx
#   - pages/
#     - Home.jsx
#     - Products.jsx
#     - Cart.jsx
#     - Checkout.jsx
#     - Profile.jsx
#   - context/
#     - AuthContext.js
#     - CartContext.js
#   - hooks/
#     - useWebSocket.js
#     - useAuth.js
#   - services/
#     - api.js
#     - websocket.js

# Backend Structure (FastAPI)
# - backend/
#   - main.py
#   - database.py
#   - models/
#     - user.py
#     - product.py
#     - order.py
#   - schemas/
#     - user.py
#     - product.py
#     - order.py
#   - routers/
#     - auth.py
#     - products.py
#     - orders.py
#     - cart.py
#   - services/
#     - payment.py
#     - notification.py
#   - websocket/
#     - connections.py

# Key implementation highlights:
# - React with Context API for state management
# - React Router for navigation
# - WebSocket integration for real-time updates
# - FastAPI with WebSocket support
# - JWT authentication with refresh tokens
# - SQLAlchemy models with relationships
# - Payment processing integration
# - Order status tracking
# - Inventory management
# - User role management""",
                "evaluation_criteria": {
                    "code_safety": {
                        "weight": 0.20,
                        "requirements": [
                            "Authentication and authorization",
                            "Input validation on both frontend and backend",
                            "SQL injection prevention",
                            "XSS protection",
                            "CSRF protection"
                        ]
                    },
                    "code_quality": {
                        "weight": 0.20,
                        "requirements": [
                            "Clean separation between frontend and backend",
                            "Proper component architecture",
                            "Consistent code style",
                            "Type safety where applicable"
                        ]
                    },
                    "functionality": {
                        "weight": 0.25,
                        "requirements": [
                            "Complete e-commerce workflow",
                            "Shopping cart functionality",
                            "User authentication and management",
                            "Product browsing and search",
                            "Order processing"
                        ]
                    },
                    "best_practices": {
                        "weight": 0.20,
                        "requirements": [
                            "RESTful API design",
                            "Responsive design principles",
                            "Error handling and loading states",
                            "Code organization and modularity",
                            "Testing implementation"
                        ]
                    },
                    "performance": {
                        "weight": 0.15,
                        "requirements": [
                            "Efficient database queries",
                            "Frontend optimization",
                            "Caching implementation",
                            "Real-time update efficiency"
                        ]
                    }
                },
                "estimated_duration_minutes": 300,
                "tags": ["fullstack", "react", "fastapi", "ecommerce", "websockets", "authentication", "advanced"]
            }
        }
    
    def get_scenarios(self, category: str = None, complexity: ComplexityLevel = None) -> List[Dict[str, Any]]:
        """Get scenarios filtered by category and/or complexity."""
        scenarios = list(self.scenarios.values())
        
        if category:
            scenarios = [s for s in scenarios if s["category"] == category]
        
        if complexity:
            scenarios = [s for s in scenarios if s["complexity_level"] == complexity]
        
        return scenarios
    
    def get_scenario_by_name(self, name: str) -> Dict[str, Any]:
        """Get a specific scenario by name."""
        return self.scenarios.get(name)
    
    def create_scenario_objects(self) -> List[EvaluationScenario]:
        """Convert scenario dictionaries to EvaluationScenario objects."""
        scenarios = []
        
        for scenario_data in self.scenarios.values():
            scenario = EvaluationScenario(
                name=scenario_data["name"],
                description=scenario_data["description"],
                category=scenario_data["category"],
                complexity_level=scenario_data["complexity_level"],
                language=scenario_data.get("language"),
                framework=scenario_data.get("framework"),
                prompt=scenario_data["prompt"],
                expected_output=scenario_data.get("expected_output"),
                evaluation_criteria=scenario_data["evaluation_criteria"],
                estimated_duration_minutes=scenario_data.get("estimated_duration_minutes"),
                tags=scenario_data.get("tags", [])
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def get_baseline_scenarios(self) -> List[Dict[str, Any]]:
        """Get scenarios suitable for baseline testing."""
        # Return a balanced set across complexity levels
        baseline_scenarios = []
        
        # Easy level - 2 scenarios
        easy_scenarios = self.get_scenarios(complexity=ComplexityLevel.EASY)[:2]
        baseline_scenarios.extend(easy_scenarios)
        
        # Medium level - 3 scenarios  
        medium_scenarios = self.get_scenarios(complexity=ComplexityLevel.MEDIUM)[:3]
        baseline_scenarios.extend(medium_scenarios)
        
        # Hard level - 2 scenarios
        hard_scenarios = self.get_scenarios(complexity=ComplexityLevel.HARD)[:2]
        baseline_scenarios.extend(hard_scenarios)
        
        return baseline_scenarios
    
    def get_regression_scenarios(self) -> List[Dict[str, Any]]:
        """Get scenarios specifically designed for regression testing."""
        # Focus on functionality and best practices
        regression_candidates = [
            "create_simple_endpoint",  # API development
            "simple_component",        # Frontend development
            "database_model",          # Database modeling
            "restful_api",             # Complex API
            "react_app",               # Frontend state management
            "microservice",            # Advanced backend
        ]
        
        return [self.get_scenario_by_name(name) for name in regression_candidates 
                if self.get_scenario_by_name(name)]