import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ProjectsComponent } from './projects.component';
import { HttpClientService } from '../core/http-client.service';
import { of, throwError } from 'rxjs';

describe('ProjectsComponent', () => {
  let component: ProjectsComponent;
  let fixture: ComponentFixture<ProjectsComponent>;
  let httpService: HttpClientService;

  beforeEach(async () => {
    const httpServiceMock = {
      get: jasmine.createSpy('get').and.callFake((url: string) => {
        if (url.includes('/repositories')) {
          return of([]);
        }
        return of([]);
      }),
      post: jasmine.createSpy('post').and.callFake((url: string, body: any) => {
        if (url.includes('/repositories')) {
          return of({ id: 'repo1', name: body.name, url: body.git_url });
        }
        return of({ id: '1', name: body.name, description: body.description });
      })
    };

    await TestBed.configureTestingModule({
      imports: [ProjectsComponent],
      providers: [
        provideRouter([]),
        { provide: HttpClientService, useValue: httpServiceMock }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ProjectsComponent);
    component = fixture.componentInstance;
    httpService = TestBed.inject(HttpClientService);
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load projects on init', () => {
    const mockProjects = [
      { id: '1', name: 'Test Project', description: 'Test description' }
    ];
    (httpService.get as jasmine.Spy).and.returnValue(of(mockProjects));

    component.ngOnInit();
    fixture.detectChanges();

    expect(httpService.get).toHaveBeenCalledWith('/projects');
  });

  it('should handle loading state', () => {
    (httpService.get as jasmine.Spy).and.returnValue(new Promise(() => {}));

    component.loadProjects();
    expect(component.loading).toBeTrue();
  });

  xit('should handle error state', async () => {
    (httpService.get as jasmine.Spy).and.returnValue(throwError(() => new Error('API error')));

    await component.loadProjects();
    fixture.detectChanges();

    expect(component.error).toBe('Failed to load projects. Please try again.');
  });

  it('should navigate to chat with project context on selection', () => {
    const routerSpy = spyOn(component['router'], 'navigate');
    const mockProject = { id: '1', name: 'Test', description: 'Test' };
    component.projectRepositories = { '1': [{ id: 'repo1', name: 'Repo', url: 'http://test.com' }] };

    component.selectProject(mockProject);

    expect(routerSpy).toHaveBeenCalledWith(['/chat'], {
      queryParams: { project_id: '1', repository_id: 'repo1' }
    });
  });

  it('should navigate to chat without repository if none exists', () => {
    const routerSpy = spyOn(component['router'], 'navigate');
    const mockProject = { id: '1', name: 'Test', description: 'Test' };
    component.projectRepositories = { '1': [] };

    component.selectProject(mockProject);

    expect(routerSpy).toHaveBeenCalledWith(['/chat'], {
      queryParams: { project_id: '1' }
    });
  });

  it('should show repository modal after creating project', async () => {
    const mockProject = { id: '1', name: 'New Project', description: 'Test' };
    (httpService.post as jasmine.Spy).and.returnValue(of(mockProject));

    component.newProject = { name: 'New Project', description: 'Test' };
    await component.createProject();

    expect(httpService.post).toHaveBeenCalledWith('/projects', jasmine.objectContaining({
      name: 'New Project',
      description: 'Test',
      organization_id: '5448f624-5af3-47b7-996a-36ce551d57ef'
    }));
    expect(component.showRepoModal).toBeTrue();
    expect(component.currentProjectId).toBe('1');
    expect(component.showCreateModal).toBeFalse();
  });

  it('should navigate to chat when skipping repository', () => {
    const routerSpy = spyOn(component['router'], 'navigate');
    component.currentProjectId = '1';

    component.skipRepository();

    expect(routerSpy).toHaveBeenCalledWith(['/chat'], {
      queryParams: { project_id: '1' }
    });
    expect(component.showRepoModal).toBeFalse();
  });

  it('should add repository and navigate to chat', async () => {
    const routerSpy = spyOn(component['router'], 'navigate');
    const mockRepo = { id: 'repo1', name: 'test-repo', url: 'https://github.com/test/repo.git' };
    (httpService.post as jasmine.Spy).and.returnValue(of(mockRepo));

    component.currentProjectId = '1';
    component.newRepo = { name: 'test-repo', git_url: 'https://github.com/test/repo.git', branch: 'main' };

    await component.addRepository();

    expect(httpService.post).toHaveBeenCalledWith('/repositories', {
      project_id: '1',
      name: 'test-repo',
      git_url: 'https://github.com/test/repo.git',
      branch: 'main'
    });
    expect(routerSpy).toHaveBeenCalledWith(['/chat'], {
      queryParams: { project_id: '1', repository_id: 'repo1' }
    });
  });
});
