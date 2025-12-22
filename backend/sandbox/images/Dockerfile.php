# PHP 8.1 sandbox base image with security hardening
FROM php:8.1-cli-alpine

# Install essential packages
RUN apk add --no-cache \
    git \
    curl \
    libzip-dev \
    oniguruma-dev \
    && docker-php-ext-install \
        opcache \
        pdo \
        pdo_mysql \
        zip

# Create sandbox user with non-root privileges
RUN addgroup -g 1000 -S sandbox && \
    adduser -S sandbox -G sandbox

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Set environment variables
ENV COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_DISABLE_GLOBAL_REQUIRES=true

# Install Composer globally
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Install PHPUnit for testing
RUN composer global require --no-interaction --no-dev phpunit/phpunit

# Create basic composer.json template
RUN echo '{"name":"sandbox/app","type":"project","require":{},"require-dev":{"phpunit/phpunit":"^10.0"},"autoload":{"psr-4":{"App\\\\":"src/"}}}' > composer.json

# Default command
CMD ["php", "index.php"]