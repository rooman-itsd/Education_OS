export type UserStatus = 'Active' | 'Pending' | 'Suspended';

export interface User {
  id: string;
  name: string;
  email: string;
  /** Role id from the academy profile, or org-admin / super-admin (see data/roles.ts). */
  role: string;
  department: string;
  status: UserStatus;
  lastLogin: string;
  avatar?: string;
  dataScope: 'Institution' | 'Department' | 'Assigned Records' | 'Self';
  phone?: string;
  employeeId?: string;
  twoFactorEnabled?: boolean;
}

export type ApplicationStatus = 'Under Review' | 'Shortlisted' | 'Confirmed' | 'Document Pending' | 'Rejected';

export interface DocumentItem {
  id: string;
  name: string;
  verified: boolean;
  type: string;
  fileSize?: string;
}

export interface TimelineStep {
  step: string;
  status: 'completed' | 'in-progress' | 'pending';
  timestamp: string;
  note?: string;
}

export interface AdmissionApplication {
  id: string;
  applicant: string;
  programme: string;
  category: 'General' | 'OBC' | 'SC/ST' | 'Sports Quota' | 'Defence';
  status: ApplicationStatus;
  submitted: string;
  email: string;
  phone: string;
  meritRank: number;
  documents: DocumentItem[];
  timeline: TimelineStep[];
  sportsDiscipline?: string;
  notes?: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  role: string;
  action: string;
  resource: string;
  status: 'Success' | 'Failed' | 'Warning';
  ipAddress: string;
}

export interface ActionRequiredItem {
  id: string;
  type: 'Payment Request' | 'Admission Application' | 'Examination Results' | 'Procurement Request' | 'RTI Application';
  referenceCode: string;
  title: string;
  description: string;
  urgency: 'Pending' | 'Urgent' | 'Review' | 'Approved';
  time: string;
  linkTo?: string;
}

export interface AlertNotification {
  id: string;
  title: string;
  subtitle: string;
  category: 'Compliance' | 'Inventory' | 'Grievance' | 'Finance' | 'System';
  severity: 'warning' | 'info' | 'critical' | 'success';
  timestamp: string;
  read?: boolean;
}

export interface UniversityEvent {
  id: string;
  day: string;
  month: string;
  title: string;
  time: string;
  category: 'Academic' | 'Exam' | 'Sports' | 'Finance' | 'Governance';
  location: string;
  filter: 'today' | 'week' | 'month';
}
