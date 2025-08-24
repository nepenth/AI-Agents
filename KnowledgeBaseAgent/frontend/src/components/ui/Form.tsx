import * as React from 'react';
import { cn } from '@/utils/cn';
import { GlassCard } from './GlassCard';
import { LiquidButton } from './LiquidButton';
import { Input } from './Input';
import { Alert, AlertDescription } from './Alert';
import { AlertTriangleIcon } from 'lucide-react';

interface FormProps extends React.FormHTMLAttributes<HTMLFormElement> {
  children: React.ReactNode;
  onSubmit?: (e: React.FormEvent<HTMLFormElement>) => void;
}

export function Form({ children, className, onSubmit, ...props }: FormProps) {
  return (
    <form
      className={cn('space-y-6', className)}
      onSubmit={onSubmit}
      {...props}
    >
      {children}
    </form>
  );
}

interface FormFieldProps {
  label?: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function FormField({ 
  label, 
  description, 
  error, 
  required, 
  children, 
  className 
}: FormFieldProps) {
  const fieldId = React.useId();
  
  return (
    <div className={cn('space-y-2', className)}>
      {label && (
        <label 
          htmlFor={fieldId}
          className="text-sm font-medium text-foreground flex items-center gap-1"
        >
          {label}
          {required && <span className="text-red-500">*</span>}
        </label>
      )}
      
      <div className="relative">
        {React.cloneElement(children as React.ReactElement, { 
          id: fieldId,
          'aria-describedby': description ? `${fieldId}-description` : undefined,
          'aria-invalid': error ? 'true' : undefined,
        })}
      </div>
      
      {description && (
        <p 
          id={`${fieldId}-description`}
          className="text-xs text-muted-foreground"
        >
          {description}
        </p>
      )}
      
      {error && (
        <Alert variant="destructive" className="py-2">
          <AlertTriangleIcon className="h-4 w-4" />
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

interface FormSectionProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function FormSection({ title, description, children, className }: FormSectionProps) {
  return (
    <GlassCard variant="tertiary" className={cn('p-6', className)}>
      {(title || description) && (
        <div className="mb-6 relative z-10">
          {title && (
            <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
          )}
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <div className="space-y-4 relative z-10">
        {children}
      </div>
    </GlassCard>
  );
}

interface FormActionsProps {
  children: React.ReactNode;
  className?: string;
  align?: 'left' | 'center' | 'right';
}

export function FormActions({ children, className, align = 'right' }: FormActionsProps) {
  const alignClasses = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
  };

  return (
    <div className={cn(
      'flex items-center gap-3 pt-4 border-t border-glass-border-tertiary',
      alignClasses[align],
      className
    )}>
      {children}
    </div>
  );
}

interface ValidationState {
  [key: string]: string | undefined;
}

interface UseFormValidationProps {
  initialValues: Record<string, any>;
  validationRules: Record<string, (value: any) => string | undefined>;
}

export function useFormValidation({ initialValues, validationRules }: UseFormValidationProps) {
  const [values, setValues] = React.useState(initialValues);
  const [errors, setErrors] = React.useState<ValidationState>({});
  const [touched, setTouched] = React.useState<Record<string, boolean>>({});

  const validateField = React.useCallback((name: string, value: any) => {
    const rule = validationRules[name];
    if (rule) {
      return rule(value);
    }
    return undefined;
  }, [validationRules]);

  const validateAll = React.useCallback(() => {
    const newErrors: ValidationState = {};
    let isValid = true;

    Object.keys(validationRules).forEach(name => {
      const error = validateField(name, values[name]);
      if (error) {
        newErrors[name] = error;
        isValid = false;
      }
    });

    setErrors(newErrors);
    return isValid;
  }, [values, validateField]);

  const setValue = React.useCallback((name: string, value: any) => {
    setValues(prev => ({ ...prev, [name]: value }));
    
    // Validate field if it has been touched
    if (touched[name]) {
      const error = validateField(name, value);
      setErrors(prev => ({ ...prev, [name]: error }));
    }
  }, [touched, validateField]);

  const setTouched = React.useCallback((name: string) => {
    setTouched(prev => ({ ...prev, [name]: true }));
    
    // Validate field when touched
    const error = validateField(name, values[name]);
    setErrors(prev => ({ ...prev, [name]: error }));
  }, [values, validateField]);

  const reset = React.useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
  }, [initialValues]);

  return {
    values,
    errors,
    touched,
    setValue,
    setTouched,
    validateAll,
    reset,
    isValid: Object.keys(errors).length === 0,
  };
}

// Common validation rules
export const validationRules = {
  required: (value: any) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return 'This field is required';
    }
    return undefined;
  },
  
  email: (value: string) => {
    if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      return 'Please enter a valid email address';
    }
    return undefined;
  },
  
  minLength: (min: number) => (value: string) => {
    if (value && value.length < min) {
      return `Must be at least ${min} characters`;
    }
    return undefined;
  },
  
  maxLength: (max: number) => (value: string) => {
    if (value && value.length > max) {
      return `Must be no more than ${max} characters`;
    }
    return undefined;
  },
  
  url: (value: string) => {
    if (value && !/^https?:\/\/.+/.test(value)) {
      return 'Please enter a valid URL';
    }
    return undefined;
  },
};