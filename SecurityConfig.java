package com.statestr.sfp.publication.config;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.core.annotation.Order;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserRequest;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserService;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

import com.statestr.sfp.publication.support.GroupsClaimMapper;
import com.statestr.sfp.publication.support.NamedOidcUser;

@Configuration
@EnableConfigurationProperties(JwtAuthorizationProperties.class)
@EnableWebSecurity
@EnableMethodSecurity(securedEnabled = true, jsr250Enabled = true)
public class SecurityConfig {

  @Value("${spring.security.oauth2.client.registration.azure.redirect-uri}")
  private String redirectUriTemplate;

  @Value("${spring.security.oauth2.client.provider.azure.jwk-set-uri}")
  private String jwkSetUri;

  @Bean
  public JwtDecoder jwtDecoder() {
    return NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();
  }

  // Bean for API endpoints (stateless, Bearer token authentication)
  
  @Bean
  @Order(1) // Higher precedence for API paths
  SecurityFilterChain apiSecurityFilterChain(HttpSecurity http) throws Exception {
    http
        .securityMatcher("/api/**") // Apply this filter chain only to /api/** paths
        .authorizeHttpRequests(authorize -> authorize
            .anyRequest().authenticated() // All API requests need to be authenticated
        )
        .oauth2ResourceServer(oauth2 -> oauth2
            .jwt(jwt -> jwt.decoder(jwtDecoder()))// Configure JWT validation (default settings, relies on
                                                  // application.properties)
        )
        .sessionManagement(session -> session
            .sessionCreationPolicy(SessionCreationPolicy.STATELESS) // APIs should be stateless
        )
        .csrf(AbstractHttpConfigurer::disable); // Typically disable CSRF for stateless APIs
    return http.build();
  }
    

  // Bean for UI/browser-based login (stateful, session-based authentication)
  @Bean
  @Order(2) // Lower precedence
  SecurityFilterChain webSecurityFilterChain(HttpSecurity http, JwtAuthorizationProperties props) throws Exception {
    // 从配置中获取允许的角色，并添加前缀
    List<String> allowedRoles = props.getAllowedRoles().stream()
        .map(role -> props.getAuthoritiesPrefix() + role)
        .collect(Collectors.toList());

    // @formatter:off
    http
      .authorizeHttpRequests(authorize -> authorize
          .requestMatchers("/access-denied", "/error").permitAll()
          // Example: Secure root path for UI users with specific roles/authorities
          .requestMatchers("/").hasAnyAuthority(allowedRoles.toArray(String[]::new))
          // Add other UI specific path rules here if needed
          .anyRequest().authenticated() // All other non-API requests also need authentication (via login)
      )
      .exceptionHandling(exceptions -> exceptions
          .accessDeniedPage("/access-denied"))
      .oauth2Login(oauth2 -> {
          oauth2.userInfoEndpoint(ep -> 
            ep.oidcUserService(customOidcUserService(props)));
          
          // Configure redirection endpoint to match custom redirect URI
          // This loginProcessingUrl might need adjustment if your redirect URI is not /secure/auth
          // oauth2.loginProcessingUrl(redirectUriTemplate); // This might be incorrect, loginProcessingUrl is usually a fixed path like /login/oauth2/code/azure
          oauth2.redirectionEndpoint(redirection -> 
            redirection.baseUri("/secure/auth")); // This is the base URI for the redirect from Azure AD
      });
      // For UI, CSRF is usually enabled by default and is good practice.
      // If you had .csrf(csrf -> csrf.disable()) before for the whole app, 
      // you might want to ensure it's enabled for this UI filter chain or rely on defaults.
    // @formatter:on
    return http.build();
  }

  private OAuth2UserService<OidcUserRequest, OidcUser> customOidcUserService(JwtAuthorizationProperties props) {
    final OidcUserService delegate = new OidcUserService();
    final GroupsClaimMapper mapper = new GroupsClaimMapper(
        props.getAuthoritiesPrefix(),
        props.getGroupsClaim(),
        props.getGroupToAuthorities());

    return (userRequest) -> {
      OidcUser oidcUser = delegate.loadUser(userRequest);
      // Enrich standard authorities with groups
      Set<GrantedAuthority> mappedAuthorities = new HashSet<>();
      mappedAuthorities.addAll(oidcUser.getAuthorities());
      mappedAuthorities.addAll(mapper.mapAuthorities(oidcUser));

      oidcUser = new NamedOidcUser(mappedAuthorities, oidcUser.getIdToken(), oidcUser.getUserInfo(),
          oidcUser.getName());

      return oidcUser;
    };
  }
}
