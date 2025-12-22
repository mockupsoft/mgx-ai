"""Template seeder for initial data population.

Populates the template system with useful pre-built templates.
"""

import logging
from typing import List, Dict, Any
from uuid import uuid4

from backend.services.templates.template_manager import TemplateManager
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility, ADRStatus

logger = logging.getLogger(__name__)


class TemplateSeeder:
    """Seeder for populating initial template data."""
    
    def __init__(self, template_manager: TemplateManager):
        """Initialize seeder with template manager."""
        self.manager = template_manager
    
    async def seed_all_templates(self) -> Dict[str, int]:
        """Seed all types of templates."""
        results = {
            "module_templates": 0,
            "prompt_templates": 0,
            "adrs": 0,
        }
        
        try:
            # Seed module templates
            results["module_templates"] = await self._seed_module_templates()
            logger.info(f"Created {results['module_templates']} module templates")
            
            # Seed prompt templates
            results["prompt_templates"] = await self._seed_prompt_templates()
            logger.info(f"Created {results['prompt_templates']} prompt templates")
            
            # Note: ADRs are workspace-specific, so we don't seed them here
            # They should be created per workspace as needed
            
        except Exception as e:
            logger.error(f"Error seeding templates: {str(e)}")
            raise
        
        return results
    
    async def _seed_module_templates(self) -> int:
        """Seed module templates."""
        module_count = 0
        
        # JWT Authentication Module
        auth_module = await self.manager.create_module_template(
            name="jwt-auth",
            category=TemplateCategory.AUTHENTICATION,
            description="JWT-based authentication module with login, registration, and token management",
            tech_stacks=["express-ts", "fastapi", "laravel"],
            dependencies=["jsonwebtoken", "bcrypt"],
            documentation="""
# JWT Authentication Module

This module provides complete JWT authentication functionality including:
- User registration with password hashing
- Login with JWT token generation
- Token validation middleware
- Password reset flow
- Refresh token support
            """.strip(),
            parameters=[
                {
                    "name": "jwtSecret",
                    "type": "string",
                    "description": "Secret key for JWT token signing",
                    "required": True,
                    "default": "your-secret-key",
                    "validation": {"minLength": 32}
                },
                {
                    "name": "tokenExpiry",
                    "type": "number",
                    "description": "Token expiry time in seconds",
                    "required": False,
                    "default": 3600,
                    "validation": {"min": 300, "max": 86400}
                },
                {
                    "name": "enableRefreshTokens",
                    "type": "boolean",
                    "description": "Enable refresh token functionality",
                    "required": False,
                    "default": True
                }
            ],
            files=[
                {
                    "path": "src/auth/routes/auth.routes.ts",
                    "content": """import { Router } from 'express';
import { AuthController } from './auth.controller';
import { authMiddleware } from '../middleware/auth.middleware';
import { validateRequest } from '../middleware/validation.middleware';

const router = Router();
const authController = new AuthController();

// Registration
router.post('/register', 
  validateRequest(authController.validateRegistration), 
  authController.register
);

// Login
router.post('/login', 
  validateRequest(authController.validateLogin), 
  authController.login
);

// Token refresh
router.post('/refresh', authController.refreshToken);

// Protected route example
router.get('/profile', authMiddleware, authController.getProfile);

// Password reset request
router.post('/forgot-password', authController.forgotPassword);

// Password reset
router.post('/reset-password/:token', authController.resetPassword);

export default router;""",
                    "language": "typescript",
                    "priority": 1
                },
                {
                    "path": "src/auth/controller/auth.controller.ts",
                    "content": """import { Request, Response } from 'express';
import { AuthService } from '../service/auth.service';
import { User } from '../models/User';
import { ValidationError } from 'express-validator';

export class AuthController {
  private authService: AuthService;

  constructor() {
    this.authService = new AuthService({
      jwtSecret: process.env.JWT_SECRET || '{{jwtSecret}}',
      tokenExpiry: {{tokenExpiry}},
      enableRefreshTokens: {{enableRefreshTokens}}
    });
  }

  validateRegistration = (req: Request): ValidationError[] => {
    // Validation logic here
    return [];
  };

  async register(req: Request, res: Response): Promise<void> {
    try {
      const { email, password, name } = req.body;
      const user = await this.authService.register({ email, password, name });
      
      res.status(201).json({
        message: 'User registered successfully',
        user: { id: user.id, email: user.email, name: user.name }
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async login(req: Request, res: Response): Promise<void> {
    try {
      const { email, password } = req.body;
      const result = await this.authService.login(email, password);
      
      res.json({
        message: 'Login successful',
        ...result
      });
    } catch (error) {
      res.status(401).json({ error: error.message });
    }
  }

  async refreshToken(req: Request, res: Response): Promise<void> {
    try {
      const { refreshToken } = req.body;
      const tokens = await this.authService.refreshTokens(refreshToken);
      
      res.json(tokens);
    } catch (error) {
      res.status(401).json({ error: error.message });
    }
  }

  async getProfile(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const user = await this.authService.getUserById(userId);
      
      res.json({ user });
    } catch (error) {
      res.status(404).json({ error: 'User not found' });
    }
  }
}""",
                    "language": "typescript",
                    "priority": 2
                },
                {
                    "path": "src/auth/middleware/auth.middleware.ts",
                    "content": """import { Request, Response, NextFunction } from 'express';
import { AuthService } from '../service/auth.service';

export const authMiddleware = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      res.status(401).json({ error: 'No token provided' });
      return;
    }

    const token = authHeader.substring(7);
    const authService = new AuthService();
    const userId = await authService.verifyToken(token);
    
    (req as any).userId = userId;
    next();
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
};""",
                    "language": "typescript",
                    "priority": 3
                }
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["authentication", "jwt", "security"]
        )
        module_count += 1
        
        # Product Catalog Module
        catalog_module = await self.manager.create_module_template(
            name="product-catalog",
            category=TemplateCategory.COMMERCE,
            description="Complete product catalog with CRUD operations, categories, search, and filtering",
            tech_stacks=["express-ts", "fastapi", "laravel"],
            dependencies=["mongoose", "elasticsearch"],
            documentation="""
# Product Catalog Module

This module provides comprehensive product catalog functionality including:
- Product CRUD operations with validation
- Category management with hierarchical structure
- Advanced search and filtering
- Image upload and management
- Pricing tiers and discounts
- Inventory tracking
            """.strip(),
            parameters=[
                {
                    "name": "maxImages",
                    "type": "number",
                    "description": "Maximum number of images per product",
                    "required": False,
                    "default": 5,
                    "validation": {"min": 1, "max": 10}
                },
                {
                    "name": "enableInventoryTracking",
                    "type": "boolean",
                    "description": "Enable inventory tracking functionality",
                    "required": False,
                    "default": True
                },
                {
                    "name": "currency",
                    "type": "string",
                    "description": "Default currency for prices",
                    "required": False,
                    "default": "USD"
                }
            ],
            files=[
                {
                    "path": "src/products/routes/products.routes.ts",
                    "content": """import { Router } from 'express';
import { ProductsController } from './products.controller';
import { upload } from '../middleware/upload.middleware';
import { authMiddleware } from '../middleware/auth.middleware';

const router = Router();
const productsController = new ProductsController();

// Public routes
router.get('/', productsController.getProducts);
router.get('/search', productsController.searchProducts);
router.get('/categories', productsController.getCategories);
router.get('/:id', productsController.getProduct);

// Protected routes
router.post('/', authMiddleware, upload.array('images', {{maxImages}}), productsController.createProduct);
router.put('/:id', authMiddleware, upload.array('images', {{maxImages}}), productsController.updateProduct);
router.delete('/:id', authMiddleware, productsController.deleteProduct);

router.post('/:id/inventory', authMiddleware, productsController.updateInventory);
router.post('/:id/pricing', authMiddleware, productsController.updatePricing);

export default router;""",
                    "language": "typescript",
                    "priority": 1
                },
                {
                    "path": "src/products/controller/products.controller.ts",
                    "content": """import { Request, Response } from 'express';
import { ProductsService } from '../service/products.service';
import { Product, ProductFilter, ProductSort } from '../types/product.types';

export class ProductsController {
  private productsService: ProductsService;

  constructor() {
    this.productsService = new ProductsService();
  }

  async getProducts(req: Request, res: Response): Promise<void> {
    try {
      const { 
        page = 1, 
        limit = 20, 
        category, 
        minPrice, 
        maxPrice, 
        inStock,
        sortBy = 'createdAt',
        sortOrder = 'desc'
      } = req.query;

      const filter: ProductFilter = {
        category: category as string,
        minPrice: minPrice ? Number(minPrice) : undefined,
        maxPrice: maxPrice ? Number(maxPrice) : undefined,
        inStock: inStock === 'true',
      };

      const sort: ProductSort = {
        [sortBy as string]: sortOrder as 'asc' | 'desc'
      };

      const result = await this.productsService.getProducts({
        page: Number(page),
        limit: Number(limit),
        filter,
        sort
      });

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async searchProducts(req: Request, res: Response): Promise<void> {
    try {
      const { q: query, ...otherParams } = req.query;
      const result = await this.productsService.searchProducts({
        query: query as string,
        ...otherParams
      });

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async getProduct(req: Request, res: Response): Promise<void> {
    try {
      const { id } = req.params;
      const product = await this.productsService.getProductById(id);
      
      if (!product) {
        res.status(404).json({ error: 'Product not found' });
        return;
      }

      res.json(product);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async createProduct(req: Request, res: Response): Promise<void> {
    try {
      const productData = req.body;
      const images = req.files as Express.Multer.File[];
      
      const product = await this.productsService.createProduct({
        ...productData,
        images: images?.map(file => ({
          url: file.path,
          alt: productData.name
        })) || []
      });

      res.status(201).json({
        message: 'Product created successfully',
        product
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async updateProduct(req: Request, res: Response): Promise<void> {
    try {
      const { id } = req.params;
      const updateData = req.body;
      const images = req.files as Express.Multer.File[];
      
      const product = await this.productsService.updateProduct(id, {
        ...updateData,
        images: images?.map(file => ({
          url: file.path,
          alt: updateData.name
        })) || undefined
      });

      res.json({
        message: 'Product updated successfully',
        product
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async updateInventory(req: Request, res: Response): Promise<void> {
    try {
      const { id } = req.params;
      const { quantity, operation = 'set' } = req.body;
      
      const product = await this.productsService.updateInventory(id, quantity, operation);
      
      res.json({
        message: 'Inventory updated successfully',
        product
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }
}""",
                    "language": "typescript",
                    "priority": 2
                }
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["products", "catalog", "ecommerce", "inventory"]
        )
        module_count += 1
        
        # Shopping Cart Module
        cart_module = await self.manager.create_module_template(
            name="shopping-cart",
            category=TemplateCategory.COMMERCE,
            description="Shopping cart functionality with item management, discounts, and session persistence",
            tech_stacks=["express-ts", "fastapi", "laravel"],
            dependencies=["redis", "mongoose"],
            documentation="""
# Shopping Cart Module

This module provides complete shopping cart functionality including:
- Add/remove items with quantity management
- Session persistence and database storage
- Discount code application
- Price calculations with taxes
- Checkout preparation
- Cart abandonment tracking
            """.strip(),
            parameters=[
                {
                    "name": "sessionTimeout",
                    "type": "number",
                    "description": "Session timeout in minutes",
                    "required": False,
                    "default": 30,
                    "validation": {"min": 5, "max": 1440}
                },
                {
                    "name": "maxItems",
                    "type": "number",
                    "description": "Maximum items per cart",
                    "required": False,
                    "default": 50,
                    "validation": {"min": 1, "max": 200}
                },
                {
                    "name": "enableDiscounts",
                    "type": "boolean",
                    "description": "Enable discount code functionality",
                    "required": False,
                    "default": True
                }
            ],
            files=[
                {
                    "path": "src/cart/routes/cart.routes.ts",
                    "content": """import { Router } from 'express';
import { CartController } from './cart.controller';
import { authMiddleware } from '../middleware/auth.middleware';

const router = Router();
const cartController = new CartController();

// Authenticated user cart
router.use(authMiddleware);

router.get('/', cartController.getCart);
router.post('/items', cartController.addItem);
router.put('/items/:productId', cartController.updateItemQuantity);
router.delete('/items/:productId', cartController.removeItem);
router.delete('/items', cartController.clearCart);

// Discount codes
router.post('/discounts', cartController.applyDiscount);
router.delete('/discounts/:code', cartController.removeDiscount);

// Cart operations
router.post('/calculate', cartController.calculateTotal);
router.post('/checkout', cartController.prepareCheckout);
router.get('/history', cartController.getCartHistory);

export default router;""",
                    "language": "typescript",
                    "priority": 1
                },
                {
                    "path": "src/cart/controller/cart.controller.ts",
                    "content": """import { Request, Response } from 'express';
import { CartService } from '../service/cart.service';
import { CartItem, DiscountCode } from '../types/cart.types';

export class CartController {
  private cartService: CartService;

  constructor() {
    this.cartService = new CartService({
      sessionTimeout: {{sessionTimeout}},
      maxItems: {{maxItems}},
      enableDiscounts: {{enableDiscounts}}
    });
  }

  async getCart(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const cart = await this.cartService.getCartByUserId(userId);
      
      res.json(cart);
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async addItem(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const { productId, quantity, variantId } = req.body;
      
      const cart = await this.cartService.addItem(userId, {
        productId,
        quantity,
        variantId
      });

      res.json({
        message: 'Item added to cart',
        cart
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async updateItemQuantity(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const { productId } = req.params;
      const { quantity } = req.body;
      
      const cart = await this.cartService.updateItemQuantity(
        userId, 
        productId, 
        quantity
      );

      res.json({
        message: 'Item quantity updated',
        cart
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async removeItem(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const { productId } = req.params;
      
      const cart = await this.cartService.removeItem(userId, productId);

      res.json({
        message: 'Item removed from cart',
        cart
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async applyDiscount(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const { code } = req.body;
      
      const cart = await this.cartService.applyDiscount(userId, code);

      res.json({
        message: 'Discount applied successfully',
        cart
      });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async calculateTotal(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const calculation = await this.cartService.calculateTotal(userId);
      
      res.json(calculation);
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }

  async prepareCheckout(req: Request, res: Response): Promise<void> {
    try {
      const userId = (req as any).userId;
      const checkoutData = await this.cartService.prepareCheckout(userId);
      
      res.json(checkoutData);
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  }
}""",
                    "language": "typescript",
                    "priority": 2
                }
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["cart", "ecommerce", "shopping", "discounts"]
        )
        module_count += 1
        
        return module_count
    
    async def _seed_prompt_templates(self) -> int:
        """Seed prompt templates."""
        template_count = 0
        
        # REST API Design Prompt
        api_prompt = await self.manager.create_prompt_template(
            name="rest-api-design",
            category=TemplateCategory.API_DESIGN,
            template="""You are designing a {{resource_type}} REST API.

Requirements:
- Endpoints: {{endpoints}}
- Authentication: {{auth_type}}
- Rate limiting: {{rate_limit}}
- Data format: {{data_format}}

Please generate:

1. OpenAPI 3.0 specification with all endpoints
2. Request/response schemas with validation rules
3. Error response formats
4. Authentication middleware code
5. Rate limiting middleware code
6. Unit test examples for each endpoint

Focus on:
- RESTful principles and best practices
- Proper HTTP status codes
- Comprehensive error handling
- Security considerations
- Performance optimization

Technology stack: {{tech_stack}}""",
            output_format=PromptOutputFormat.CODE,
            context_required=["resource_type", "endpoints", "auth_type", "rate_limit", "data_format", "tech_stack"],
            examples=[
                "Generate REST API for User management with CRUD operations, JWT auth, and 1000 req/min rate limit",
                "Generate REST API for Product catalog with OAuth2, search endpoints, and 500 req/min rate limit"
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["api", "rest", "design", "openapi"]
        )
        template_count += 1
        
        # Database Schema Prompt
        db_prompt = await self.manager.create_prompt_template(
            name="database-schema",
            category=TemplateCategory.DATABASE,
            template="""Design a database schema for {{domain}}.

Entities to include: {{entities}}
Relationships: {{relationships}}
Constraints: {{constraints}}
Performance requirements: {{performance_requirements}}

Please generate:

1. SQL CREATE TABLE statements with proper data types
2. Primary and foreign key constraints
3. Indexes for optimal query performance
4. Check constraints for data validation
5. Sample INSERT statements for testing
6. Query examples for common operations

Consider:
- Normalization principles
- Scalability and performance
- Data integrity and constraints
- Appropriate indexing strategy
- Backup and recovery considerations

Database: {{database_type}}""",
            output_format=PromptOutputFormat.CODE,
            context_required=["domain", "entities", "relationships", "constraints", "performance_requirements", "database_type"],
            examples=[
                "Design schema for E-commerce with Users, Products, Orders, and Inventory with high read performance",
                "Design schema for Social Media with Users, Posts, Comments, and Likes with real-time features"
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["database", "sql", "schema", "normalization"]
        )
        template_count += 1
        
        # Test Strategy Prompt
        test_prompt = await self.manager.create_prompt_template(
            name="test-strategy",
            category=TemplateCategory.TESTING,
            template="""Create a comprehensive testing strategy for {{system_type}}.

Coverage target: {{coverage_percent}}%
Priority testing areas: {{priority_areas}}
Technology stack: {{tech_stack}}
Deployment environment: {{environment}}

Please provide:

1. Test pyramid structure (unit, integration, e2e)
2. Testing framework recommendations
3. Test data management strategy
4. Continuous integration test pipeline
5. Performance testing approach
6. Security testing checklist
7. Test automation coverage matrix
8. Quality gates and success criteria

Include:
- Specific test examples for {{system_type}}
- Mock data and fixtures setup
- Test environment configuration
- Performance benchmarks
- Security vulnerability tests""",
            output_format=PromptOutputFormat.DOCUMENTATION,
            context_required=["system_type", "coverage_percent", "priority_areas", "tech_stack", "environment"],
            examples=[
                "Testing strategy for REST API with 90% coverage, focusing on authentication and data validation",
                "Testing strategy for E-commerce platform with 95% coverage, emphasizing payment flows and inventory"
            ],
            author="Template System",
            visibility=TemplateVisibility.PUBLIC,
            tags=["testing", "qa", "automation", "strategy"]
        )
        template_count += 1
        
        return template_count