/**
 * Accessibility testing utilities for development and testing environments
 */

interface AccessibilityIssue {
  type: 'error' | 'warning' | 'info'
  rule: string
  message: string
  element: HTMLElement
  suggestion?: string
}

export class AccessibilityTester {
  private issues: AccessibilityIssue[] = []

  /**
   * Run basic accessibility checks on the current page
   */
  async runBasicChecks(): Promise<AccessibilityIssue[]> {
    this.issues = []
    
    // Check for missing alt text on images
    this.checkImageAltText()
    
    // Check for proper heading hierarchy
    this.checkHeadingHierarchy()
    
    // Check for form labels
    this.checkFormLabels()
    
    // Check for keyboard accessibility
    this.checkKeyboardAccessibility()
    
    // Check for color contrast (basic check)
    this.checkColorContrast()
    
    // Check for ARIA attributes
    this.checkAriaAttributes()
    
    // Check for focus management
    this.checkFocusManagement()
    
    return this.issues
  }

  private checkImageAltText() {
    const images = document.querySelectorAll('img')
    
    images.forEach(img => {
      if (!img.hasAttribute('alt')) {
        this.addIssue({
          type: 'error',
          rule: 'img-alt',
          message: 'Image missing alt attribute',
          element: img,
          suggestion: 'Add descriptive alt text or alt="" for decorative images'
        })
      } else if (img.getAttribute('alt') === '' && !img.hasAttribute('role')) {
        // Empty alt is okay for decorative images, but check if it should be decorative
        const hasAriaLabel = img.hasAttribute('aria-label') || img.hasAttribute('aria-labelledby')
        if (!hasAriaLabel) {
          this.addIssue({
            type: 'info',
            rule: 'img-alt-empty',
            message: 'Image has empty alt text - ensure this is decorative',
            element: img,
            suggestion: 'If decorative, consider adding role="presentation"'
          })
        }
      }
    })
  }

  private checkHeadingHierarchy() {
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6')
    let previousLevel = 0
    
    headings.forEach(heading => {
      const currentLevel = parseInt(heading.tagName.charAt(1))
      
      if (currentLevel > previousLevel + 1) {
        this.addIssue({
          type: 'warning',
          rule: 'heading-hierarchy',
          message: `Heading level skipped from h${previousLevel} to h${currentLevel}`,
          element: heading,
          suggestion: 'Use sequential heading levels for proper document structure'
        })
      }
      
      previousLevel = currentLevel
    })
    
    // Check for missing h1
    const h1Elements = document.querySelectorAll('h1')
    if (h1Elements.length === 0) {
      this.addIssue({
        type: 'warning',
        rule: 'missing-h1',
        message: 'Page missing h1 element',
        element: document.body,
        suggestion: 'Add an h1 element to provide a main heading for the page'
      })
    } else if (h1Elements.length > 1) {
      h1Elements.forEach((h1, index) => {
        if (index > 0) {
          this.addIssue({
            type: 'warning',
            rule: 'multiple-h1',
            message: 'Multiple h1 elements found',
            element: h1,
            suggestion: 'Consider using h2-h6 for subheadings'
          })
        }
      })
    }
  }

  private checkFormLabels() {
    const inputs = document.querySelectorAll('input, select, textarea')
    
    inputs.forEach(input => {
      const hasLabel = this.hasAssociatedLabel(input as HTMLElement)
      const hasAriaLabel = input.hasAttribute('aria-label') || input.hasAttribute('aria-labelledby')
      
      if (!hasLabel && !hasAriaLabel) {
        this.addIssue({
          type: 'error',
          rule: 'form-label',
          message: 'Form control missing accessible label',
          element: input as HTMLElement,
          suggestion: 'Add a <label> element or aria-label attribute'
        })
      }
    })
  }

  private hasAssociatedLabel(element: HTMLElement): boolean {
    const id = element.getAttribute('id')
    if (id) {
      const label = document.querySelector(`label[for="${id}"]`)
      if (label) return true
    }
    
    // Check if wrapped in label
    const parentLabel = element.closest('label')
    return !!parentLabel
  }

  private checkKeyboardAccessibility() {
    const interactiveElements = document.querySelectorAll(
      'button, a[href], input, select, textarea, [tabindex], [role="button"], [role="link"]'
    )
    
    interactiveElements.forEach(element => {
      const tabIndex = element.getAttribute('tabindex')
      
      // Check for positive tabindex (anti-pattern)
      if (tabIndex && parseInt(tabIndex) > 0) {
        this.addIssue({
          type: 'warning',
          rule: 'positive-tabindex',
          message: 'Positive tabindex found - can disrupt natural tab order',
          element: element as HTMLElement,
          suggestion: 'Use tabindex="0" or remove tabindex to maintain natural order'
        })
      }
      
      // Check for missing keyboard event handlers on custom interactive elements
      if (element.hasAttribute('role') && 
          (element.getAttribute('role') === 'button' || element.getAttribute('role') === 'link')) {
        const hasKeyHandler = element.hasAttribute('onkeydown') || 
                             element.hasAttribute('onkeyup') || 
                             element.hasAttribute('onkeypress')
        
        if (!hasKeyHandler) {
          this.addIssue({
            type: 'warning',
            rule: 'keyboard-handler',
            message: 'Custom interactive element may not be keyboard accessible',
            element: element as HTMLElement,
            suggestion: 'Add keyboard event handlers for Enter and Space keys'
          })
        }
      }
    })
  }

  private checkColorContrast() {
    // Basic color contrast check (simplified)
    const textElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6, a, button, label')
    
    textElements.forEach(element => {
      const styles = window.getComputedStyle(element)
      const fontSize = parseFloat(styles.fontSize)
      const fontWeight = styles.fontWeight
      
      // Check if text is large (18pt+ or 14pt+ bold)
      const isLargeText = fontSize >= 18 || (fontSize >= 14 && (fontWeight === 'bold' || parseInt(fontWeight) >= 700))
      
      // This is a simplified check - in practice, you'd calculate actual contrast ratios
      const backgroundColor = styles.backgroundColor
      const color = styles.color
      
      if (backgroundColor === 'rgba(0, 0, 0, 0)' || backgroundColor === 'transparent') {
        // Inherit from parent - this is a simplified check
        return
      }
      
      // Add warning for potential contrast issues (this would need actual color calculation)
      if (color === backgroundColor) {
        this.addIssue({
          type: 'error',
          rule: 'color-contrast',
          message: 'Text and background colors are the same',
          element: element as HTMLElement,
          suggestion: 'Ensure sufficient color contrast between text and background'
        })
      }
    })
  }

  private checkAriaAttributes() {
    const elementsWithAria = document.querySelectorAll('[aria-labelledby], [aria-describedby]')
    
    elementsWithAria.forEach(element => {
      const labelledBy = element.getAttribute('aria-labelledby')
      const describedBy = element.getAttribute('aria-describedby')
      
      if (labelledBy) {
        const labelIds = labelledBy.split(' ')
        labelIds.forEach(id => {
          if (!document.getElementById(id)) {
            this.addIssue({
              type: 'error',
              rule: 'aria-labelledby',
              message: `aria-labelledby references non-existent element with id="${id}"`,
              element: element as HTMLElement,
              suggestion: 'Ensure referenced element exists or remove invalid reference'
            })
          }
        })
      }
      
      if (describedBy) {
        const descriptionIds = describedBy.split(' ')
        descriptionIds.forEach(id => {
          if (!document.getElementById(id)) {
            this.addIssue({
              type: 'error',
              rule: 'aria-describedby',
              message: `aria-describedby references non-existent element with id="${id}"`,
              element: element as HTMLElement,
              suggestion: 'Ensure referenced element exists or remove invalid reference'
            })
          }
        })
      }
    })
    
    // Check for required ARIA attributes
    const elementsWithRoles = document.querySelectorAll('[role]')
    elementsWithRoles.forEach(element => {
      const role = element.getAttribute('role')
      
      switch (role) {
        case 'button':
          if (!element.hasAttribute('aria-label') && 
              !element.hasAttribute('aria-labelledby') && 
              !element.textContent?.trim()) {
            this.addIssue({
              type: 'error',
              rule: 'button-name',
              message: 'Button element missing accessible name',
              element: element as HTMLElement,
              suggestion: 'Add aria-label, aria-labelledby, or text content'
            })
          }
          break
        
        case 'img':
          if (!element.hasAttribute('aria-label') && !element.hasAttribute('aria-labelledby')) {
            this.addIssue({
              type: 'error',
              rule: 'img-name',
              message: 'Image role element missing accessible name',
              element: element as HTMLElement,
              suggestion: 'Add aria-label or aria-labelledby attribute'
            })
          }
          break
      }
    })
  }

  private checkFocusManagement() {
    // Check for elements that should be focusable but aren't
    const interactiveElements = document.querySelectorAll('[role="button"], [role="link"], [onclick]')
    
    interactiveElements.forEach(element => {
      const tabIndex = element.getAttribute('tabindex')
      const isNativelyFocusable = element.matches('button, a[href], input, select, textarea')
      
      if (!isNativelyFocusable && (!tabIndex || tabIndex === '-1')) {
        this.addIssue({
          type: 'warning',
          rule: 'focusable-element',
          message: 'Interactive element is not keyboard focusable',
          element: element as HTMLElement,
          suggestion: 'Add tabindex="0" to make element focusable'
        })
      }
    })
  }

  private addIssue(issue: AccessibilityIssue) {
    this.issues.push(issue)
  }

  /**
   * Generate a report of accessibility issues
   */
  generateReport(): string {
    const errorCount = this.issues.filter(issue => issue.type === 'error').length
    const warningCount = this.issues.filter(issue => issue.type === 'warning').length
    const infoCount = this.issues.filter(issue => issue.type === 'info').length
    
    let report = `Accessibility Report\n`
    report += `==================\n\n`
    report += `Summary: ${errorCount} errors, ${warningCount} warnings, ${infoCount} info\n\n`
    
    if (this.issues.length === 0) {
      report += `No accessibility issues found!\n`
      return report
    }
    
    const groupedIssues = this.issues.reduce((groups, issue) => {
      if (!groups[issue.type]) {
        groups[issue.type] = []
      }
      groups[issue.type].push(issue)
      return groups
    }, {} as Record<string, AccessibilityIssue[]>)
    
    Object.entries(groupedIssues).forEach(([type, issues]) => {
      report += `${type.toUpperCase()}S:\n`
      report += `${'='.repeat(type.length + 2)}\n\n`
      
      issues.forEach((issue, index) => {
        report += `${index + 1}. ${issue.message}\n`
        report += `   Rule: ${issue.rule}\n`
        report += `   Element: ${issue.element.tagName.toLowerCase()}`
        
        if (issue.element.id) {
          report += `#${issue.element.id}`
        }
        
        if (issue.element.className) {
          report += `.${issue.element.className.split(' ').join('.')}`
        }
        
        report += `\n`
        
        if (issue.suggestion) {
          report += `   Suggestion: ${issue.suggestion}\n`
        }
        
        report += `\n`
      })
    })
    
    return report
  }

  /**
   * Clear all recorded issues
   */
  clearIssues() {
    this.issues = []
  }
}

// Development-only accessibility testing
if (import.meta.env?.DEV) {
  const accessibilityTester = new AccessibilityTester()
  
  // Make accessibility tester available in development console
  ;(window as any).accessibilityTester = accessibilityTester
  
  console.log('Accessibility testing utilities available at window.accessibilityTester')
  console.log('Available methods:')
  console.log('- accessibilityTester.runBasicChecks()')
  console.log('- accessibilityTester.generateReport()')
  console.log('- accessibilityTester.clearIssues()')
}

export { AccessibilityTester }